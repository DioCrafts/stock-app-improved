"""Wrapper sobre la API pública de SEC EDGAR — ÚNICO punto que habla con la SEC.

Análogo a `yfinance_client.py` pero para datos de insiders (Section 16, Form 3/4/5):
reintentos + caché TTL + rate-limit, para poder mockearlo o cambiarlo sin tocar el resto.

Fuentes (todas gratuitas, sin API key; requieren User-Agent y <10 req/s):
- Mapeo ticker→CIK:   https://www.sec.gov/files/company_tickers.json
- Historial filings:  https://data.sec.gov/submissions/CIK##########.json
- Documentos:         https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/...
- Backfill histórico: https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{Y}q{Q}_form345.zip

El parsing vive en `ingest/insider_mappers.py` (puro y testeable). Aquí solo red.
La SEC exige un User-Agent identificable (configúralo en SEC_USER_AGENT con tu email,
por su política de "fair access"): https://www.sec.gov/os/webmaster-faq#developers
"""
from __future__ import annotations

import csv
import io
import threading
import time
import zipfile
from typing import Callable

import httpx

from app.cache.store import memoize
from app.config import settings
from app.ingest.insider_mappers import parse_form4_xml, transactions_from_dera

_BASE_WWW = "https://www.sec.gov"
_BASE_DATA = "https://data.sec.gov"
_DERA_URL = _BASE_WWW + "/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"

_MIN_INTERVAL = 0.15  # s entre peticiones (~6-7 req/s, holgura bajo el límite de 10/s)
_lock = threading.Lock()
_last_request = 0.0


def _headers() -> dict[str, str]:
    return {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}


def _throttle() -> None:
    """Serializa peticiones respetando un intervalo mínimo (política de la SEC)."""
    global _last_request
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _retry(fn: Callable, attempts: int = 3, base_delay: float = 1.0):
    """Reintenta `fn` ante errores transitorios (rate-limit/red), como yfinance_client."""
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 — se relanza el último
            last_err = err
            if i < attempts - 1:
                time.sleep(base_delay * (i + 1))
    raise last_err  # type: ignore[misc]


def _get_json(url: str) -> dict:
    def fetch() -> dict:
        _throttle()
        r = httpx.get(url, headers=_headers(), timeout=30, follow_redirects=True)
        r.raise_for_status()
        return r.json()
    return _retry(fetch)


def _get_text(url: str) -> str:
    def fetch() -> str:
        _throttle()
        r = httpx.get(url, headers=_headers(), timeout=30, follow_redirects=True)
        r.raise_for_status()
        return r.text
    return _retry(fetch)


# --------------------------------------------------------------------------- #
# Ticker → CIK
# --------------------------------------------------------------------------- #

def get_cik_map() -> dict[str, str]:
    """{ticker → CIK 10 dígitos} desde company_tickers.json (cacheado 24h)."""
    def build() -> dict[str, str]:
        data = _get_json(_BASE_WWW + "/files/company_tickers.json")
        out: dict[str, str] = {}
        for row in data.values():
            tic = str(row.get("ticker", "")).upper()
            cik = str(row.get("cik_str", "")).zfill(10)
            if tic:
                out[tic] = cik
        return out
    return memoize("edgar:cik_map", build, ttl=86400)


def get_cik(ticker: str) -> str | None:
    """CIK (10 díg.) para un símbolo estilo yfinance. La SEC usa '-' para clases
    (BRK-B); probamos variantes por si acaso."""
    t = ticker.strip().upper()
    cmap = get_cik_map()
    for cand in (t, t.replace(".", "-"), t.replace("-", "."), t.split(".")[0]):
        if cand in cmap:
            return cmap[cand]
    return None


# --------------------------------------------------------------------------- #
# Filings recientes (Form 4) vía submissions API
# --------------------------------------------------------------------------- #

def recent_ownership_filings(cik: str, max_filings: int = 60) -> list[dict]:
    """Últimos Form 3/4/5 de un emisor: [{accession, filing_date, primary_doc, form}]."""
    data = _get_json(f"{_BASE_DATA}/submissions/CIK{cik}.json")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])
    out: list[dict] = []
    for i, form in enumerate(forms):
        if form not in ("3", "4", "5", "3/A", "4/A", "5/A"):
            continue
        out.append({
            "accession": accs[i] if i < len(accs) else None,
            "filing_date": dates[i] if i < len(dates) else None,
            "primary_doc": docs[i] if i < len(docs) else None,
            "form": form,
        })
        if len(out) >= max_filings:
            break
    return out


def _archive_dir(cik: str, accession: str) -> str:
    return f"{_BASE_WWW}/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"


def _locate_ownership_xml(cik: str, accession: str, primary_doc: str | None) -> str | None:
    """URL del XML "ownershipDocument" del filing. Usa el primary_doc si ya es XML
    crudo; si no, consulta index.json y elige el .xml que no sea la hoja de estilo (xsl)."""
    base = _archive_dir(cik, accession)
    if primary_doc and primary_doc.endswith(".xml") and not primary_doc.startswith("xsl"):
        return f"{base}/{primary_doc}"
    try:
        idx = _get_json(f"{base}/index.json")
    except Exception:  # noqa: BLE001 — sin índice → no se puede localizar
        return None
    for item in idx.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.endswith(".xml") and not name.startswith("xsl"):
            return f"{base}/{name}"
    return None


def fetch_insider_transactions(ticker: str, max_filings: int = 60) -> list[dict]:
    """Transacciones de insiders de un ticker, en vivo desde EDGAR (normalizadas).

    Resultado cacheado (TTL 6h): los Form 4 cambian despacio y evita martillear la SEC.
    Devuelve [] si el ticker no tiene CIK (p. ej. no-US) o no hay filings.
    """
    def build() -> list[dict]:
        cik = get_cik(ticker)
        if not cik:
            return []
        out: list[dict] = []
        for f in recent_ownership_filings(cik, max_filings=max_filings):
            acc = f["accession"]
            xml_url = _locate_ownership_xml(cik, acc, f.get("primary_doc"))
            if not xml_url:
                continue
            try:
                xml = _get_text(xml_url)
            except Exception:  # noqa: BLE001 — un filing roto no aborta el resto
                continue
            out.extend(parse_form4_xml(
                xml, symbol=ticker.upper(), accession=acc,
                url=f"{_archive_dir(cik, acc)}/"))
        return out
    return memoize(f"edgar:txns:{ticker.upper()}:{max_filings}", build, ttl=21600)


# --------------------------------------------------------------------------- #
# Backfill histórico — datasets trimestrales DERA "Form 345"
# --------------------------------------------------------------------------- #

def _read_tsv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    try:
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
            return list(csv.DictReader(text, delimiter="\t"))
    except KeyError:
        return []


def fetch_dera_quarter(year: int, quarter: int, symbols: set[str] | None = None) -> list[dict]:
    """Descarga el ZIP trimestral DERA y devuelve transacciones normalizadas.

    `symbols` filtra al universo (un trimestre trae ~cientos de miles de filas).
    Pensado para el backfill histórico (uso puntual, no en caliente).
    """
    url = _DERA_URL.format(y=year, q=quarter)
    _throttle()
    r = httpx.get(url, headers=_headers(), timeout=120, follow_redirects=True)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        return transactions_from_dera(
            _read_tsv(zf, "SUBMISSION.tsv"),
            _read_tsv(zf, "REPORTINGOWNER.tsv"),
            _read_tsv(zf, "NONDERIV_TRANS.tsv"),
            _read_tsv(zf, "DERIV_TRANS.tsv"),
            symbols=symbols,
        )
