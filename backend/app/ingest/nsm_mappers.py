"""Parser PURO de las notificaciones PDMR del FCA NSM (Reino Unido) → dicts normalizados.

Las notificaciones del Artículo 19 de UK MAR siguen la plantilla estándar
(Reglamento de Ejecución (UE) 2016/523): un documento HTML (exportado de Word) con
secciones fijas 1–4. Este módulo extrae los campos por anclas de texto robustas y
los normaliza al MISMO formato que los parsers de la SEC (insider_mappers), para que
fluyan por las mismas tablas/métricas/endpoint/widget.

Formato normalizado (igual que SEC) + `currency` (la divisa se decide a nivel UK):
    symbol, cik(None), accession, filer, relationship, txn_date (ISO), code, action,
    shares, price, shares_after(None), ownership(None), is_derivative(False), url, currency

Limitaciones conocidas (HTML de Word, plantilla con variantes):
- Se extrae UN registro agregado por documento (si trae varias filas de precio se
  agregan a volumen total + precio medio); los importes son best-effort y caen a None
  si la plantilla no casa (los recuentos compra/venta siguen siendo correctos).
- El mapeo "naturaleza → compra/venta" es heurístico (MAR no usa códigos como la SEC).
"""
from __future__ import annotations

import html as _html
import re

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})

# Sufijos societarios a eliminar para casar el nombre del emisor con el universo.
_SUFFIX_RE = re.compile(r"\b(PLC|LIMITED|LTD|LLP|INC|CORP|CORPORATION|COMPANY|CO|HOLDINGS|"
                        r"GROUP|AG|NV|SA|SE)\b")
_ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")
_LEI_RE = re.compile(r"\bLEI(?:\s*code)?\b\s*:?\s*([0-9A-Z]{20})\b", re.I)


def normalize_company_name(name: str | None) -> str:
    """Nombre de empresa → clave canónica para casar NSM↔universo (sin sufijos/puntuación)."""
    if not name:
        return ""
    s = name.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _SUFFIX_RE.sub(" ", s)
    return re.sub(r"\s+", "", s)


# Naturaleza (texto libre MAR) → (action, code SEC-like). El orden importa: el "ruido"
# (impuestos/ejercicio/concesión/transferencia) se detecta ANTES que compra/venta, para
# no contar como convicción una venta para cubrir impuestos o un ejercicio de opciones.
def nature_to_action(nature: str | None) -> tuple[str, str]:
    # Patrones por raíz con \b SOLO al inicio (permite sufijos: acqui→acquisition,
    # dispos→disposal). El orden importa: el "ruido" va antes que compra/venta.
    t = (nature or "").lower()
    if not t:
        return ("other", "J")
    if re.search(r"\b(tax|withhold|to cover|cover the|sufficient shares)", t):
        return ("tax", "F")
    if re.search(r"\b(option|exercise)", t):
        return ("exercise", "M")
    if re.search(r"\b(award|grant|vest|conditional|deferred|rsu|restricted|scrip|dividend)", t):
        return ("grant", "A")
    if re.search(r"\btransfer", t):
        return ("other", "J")
    if re.search(r"\b(dispos|sale|sold|sell)", t):
        return ("sell", "S")
    if re.search(r"\b(acqui|purchas|bought|buy|subscri)", t):
        return ("buy", "P")
    return ("other", "J")


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]*>", " ", html)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    compact = re.sub(r"\s+", "", raw)            # "2026- 06-15" (artefacto Word) → "2026-06-15"
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", compact)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", compact)  # dd/mm/yyyy
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)       # 17 June 2026
    if m:
        d, mon, y = m.groups()
        mi = _MONTHS.get(mon.lower())
        if mi:
            return f"{y}-{mi:02d}-{int(d):02d}"
    return None


def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _finalize_pv(shares: float, price: float, pence: bool) -> tuple[float, float]:
    return (round(shares, 4), round(price / 100 if pence else price, 6))


def _parse_price_volume(seg: str, pence: bool) -> tuple[float | None, float | None]:
    """(shares, price en libras) desde la sub-tabla precio/volumen. Maneja 3 variantes
    de plantilla MAR y agrega filas (VWAP). None si ninguna casa (los recuentos no se ven
    afectados)."""
    # 1) LSEG estándar: '<precio> GBP <volumen> <total> GBP'
    triplets = re.findall(
        r"([\d,]+(?:\.\d+)?)\s*GB[PX]\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s*GB[PX]",
        seg, re.I)
    vol = val = 0.0
    for _p, v, total in triplets:
        vv, tt = _to_float(v), _to_float(total)
        if vv and tt:
            vol += vv
            val += tt
    if vol and val:
        return _finalize_pv(vol, val / vol, pence)

    # 2) Multi-fill con divisa pegada al precio: 'GBP<precio> <volumen>' por ejecución
    pairs = re.findall(r"GB[PX]\s*([\d,]+\.\d+)\s+([\d,]+(?:\.\d+)?)", seg, re.I)
    vol = val = 0.0
    for p, v in pairs:
        pp, vv = _to_float(p), _to_float(v)
        if pp is not None and vv:
            vol += vv
            val += pp * vv
    if vol and val:
        return _finalize_pv(vol, val / vol, pence)

    # 3) Sección 'Aggregated information': '<volumen agregado> GBP<precio medio>'
    m = re.search(r"Aggregated[^\d]*([\d,]+(?:\.\d+)?)\s*GB[PX]\s*([\d.]+)", seg, re.I)
    if m:
        vv, pp = _to_float(m.group(1)), _to_float(m.group(2))
        if vv and pp is not None:
            return _finalize_pv(vv, pp, pence)
    return (None, None)


def parse_nsm_document(html: str, *, symbol: str | None = None, company: str | None = None,
                       lei: str | None = None, accession: str | None = None,
                       url: str | None = None) -> list[dict]:
    """Documento HTML de una notificación PDMR → [transacción normalizada]. [] si no parsea."""
    text = _html_to_text(html)
    if "nature of the transaction" not in text.lower():
        return []

    # Nombre del PDMR (sección 1, entre "1 Details of the…" y "2 Reason")
    name = None
    m = re.search(r"1\s+Details of the.*?\b(?:Full name|Name)\b\s*:?\s*(.+?)\s+2\s+Reason",
                  text, re.I | re.S)
    if m:
        name = m.group(1).strip(" :.-")

    # Cargo (sección 2)
    relationship = None
    m = re.search(r"2\s+Reason for the notification(.*?)3\s+Details", text, re.I | re.S)
    if m:
        sec2 = m.group(1)
        parts: list[str] = []
        p = re.search(r"Position\s*/?\s*status\s*:?\s*(.+?)\s+(?:b\)|Initial|Job\s+title|$)",
                      sec2, re.I)
        if p:
            parts.append(p.group(1).strip(" :.-"))
        j = re.search(r"Job\s*title\s*/?\s*function\s*:?\s*(.+?)$", sec2, re.I)
        if j:
            parts.append(j.group(1).strip(" :.-"))
        relationship = ", ".join(x for x in parts if x) or None

    # Sección 4 (transacción): ISIN, naturaleza, divisa, precio/volumen, fecha
    sec4 = text
    m = re.search(r"4\s+Details of the transaction(.*)$", text, re.I | re.S)
    if m:
        sec4 = m.group(1)

    isin_m = _ISIN_RE.search(sec4)
    isin = isin_m.group(1) if isin_m else None

    nat = re.search(r"[Nn]ature of the transactions?\s*:?\s*(.+?)\s+"
                    r"(?:[a-g]\)\s*(?:Currency|Price|Aggregated|Date)|Currency\s*[:\-]|"
                    r"Price\s*\(?s?\)?\s*(?:&|and)?\s*[Vv]olume|Date of)", sec4, re.I | re.S)
    nature = nat.group(1).strip(" :.-") if nat else None
    action, code = nature_to_action(nature)

    cur_m = re.search(r"Currency\s*:?\s*([A-Za-z]{3})", sec4)
    cur = cur_m.group(1) if cur_m else "GBP"
    pence = cur.upper() == "GBX" or cur == "GBp" or "GBX" in sec4 or "pence" in sec4.lower()

    # Precio/volumen: toda la sección 4 hasta la fecha/lugar (cubre varias etiquetas de tabla)
    pv_seg = re.split(r"Date of (?:the )?transaction|Place of (?:the )?transaction",
                      sec4, maxsplit=1, flags=re.I)[0]
    shares, price = _parse_price_volume(pv_seg, pence)

    dt = re.search(r"Date of (?:the )?transaction\s*:?\s*"
                   r"(\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{4}|"
                   r"\d{1,2}\s+[A-Za-z]+\s+\d{4})", sec4, re.I)
    txn_date = _parse_date(dt.group(1) if dt else None)

    return [{
        "symbol": (symbol or "").upper() or None,
        "cik": None,
        "accession": accession,
        "filer": name or "Unknown",
        "relationship": relationship,
        "txn_date": txn_date,
        "code": code,
        "action": action,
        "shares": shares,
        "price": price,
        "shares_after": None,
        "ownership": None,
        "is_derivative": False,
        "url": url,
        "isin": isin,
        "lei": lei,
        "currency": "GBP",
    }]
