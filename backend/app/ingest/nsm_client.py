"""Wrapper sobre la API pública del FCA National Storage Mechanism (NSM) — UK.

ÚNICO punto que habla con data.fca.org.uk (análogo a edgar_client para EE.UU.).
El NSM es el repositorio oficial de información regulada del Reino Unido (DTR 6) —
el equivalente a SEC EDGAR — y expone una API de búsqueda Elasticsearch pública y
SIN autenticación (la misma que usa su buscador web):

- Búsqueda:  POST https://api.data.fca.org.uk/search?index=fca-nsm-searchdata
             body {from,size,sort:"publication_date",sortorder,keyword:"PDMR",criteriaObj:null}
- Documento: GET  https://data.fca.org.uk/artefacts/{download_link}   (plantilla MAR)

El parsing del documento vive en `ingest/nsm_mappers.py` (puro y testeable). Aquí solo red.
Es un endpoint interno (no una API con términos publicados): rate-limit educado, User-Agent
identificable y parsing tolerante por si cambia. El NSM no es tiempo real (~48h de retraso).
"""
from __future__ import annotations

import threading
import time
from typing import Callable

import httpx

from app.cache.store import memoize
from app.config import settings

_SEARCH_API = "https://api.data.fca.org.uk/search"
_NSM_INDEX = "fca-nsm-searchdata"
_ARTEFACT_BASE = "https://data.fca.org.uk/artefacts/"

_MIN_INTERVAL = 0.2  # s entre peticiones (educado con un servicio del regulador)
_lock = threading.Lock()
_last_request = 0.0


def _throttle() -> None:
    global _last_request
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _retry(fn: Callable, attempts: int = 3, base_delay: float = 1.0):
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 — se relanza el último
            last_err = err
            if i < attempts - 1:
                time.sleep(base_delay * (i + 1))
    raise last_err  # type: ignore[misc]


def search_pdmr_page(from_: int = 0, size: int = 100) -> tuple[int, list[dict]]:
    """Una página de notificaciones PDMR (orden publicación desc). Devuelve (total, [_source]).

    `_source` trae metadatos: company, lei, type_code, headline, publication_date,
    download_link, disclosure_id. NO se cachea (los resultados cambian)."""
    body = {
        "from": from_, "size": size,
        "sort": "publication_date", "sortorder": "desc",
        "keyword": "PDMR", "criteriaObj": None,
    }

    def fetch() -> dict:
        _throttle()
        r = httpx.post(_SEARCH_API, params={"index": _NSM_INDEX}, json=body,
                       headers={"User-Agent": settings.nsm_user_agent}, timeout=30)
        r.raise_for_status()
        return r.json()

    data = _retry(fetch)
    hits = data.get("hits", {})
    total = (hits.get("total") or {}).get("value") or 0
    return int(total), [h.get("_source", {}) for h in hits.get("hits", [])]


def artefact_url(download_link: str) -> str:
    """URL pública del documento (para guardar como enlace de la operación)."""
    return _ARTEFACT_BASE + download_link.lstrip("/")


def fetch_artefact(download_link: str) -> str:
    """HTML del documento de la notificación. Cacheado 7d (los artefacts son inmutables)."""
    url = artefact_url(download_link)

    def fetch() -> str:
        _throttle()
        r = httpx.get(url, headers={"User-Agent": settings.nsm_user_agent},
                      timeout=30, follow_redirects=True)
        r.raise_for_status()
        return r.text

    return memoize(f"nsm:doc:{download_link}", lambda: _retry(fetch), ttl=604800)
