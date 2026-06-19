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


def _clean_money(seg: str) -> str:
    """Corrige artefactos de Word: '£ 100' → '£100' y '0. 76' → '0.76'."""
    seg = re.sub(r"£\s+", "£", seg)
    return re.sub(r"(\d)\.\s+(\d)", r"\1.\2", seg)


# Unidades de precio (orden: la más específica primero). p/pence/gbx = peniques.
_PRICE_UNIT = r"(?:pence per share|pence|gbx|gbp|p|£)"


def _unit_pence(u: str) -> bool:
    u = u.strip().lower()
    return u in ("p", "pence", "gbx") or u.startswith("pence")


def _rows_suffix(region: str) -> tuple[float, float]:
    """Filas 'precio<unidad> volumen' (divisa sufijo): 60p 15,000 · 11.66 GBP 1,574 ·
    4412 pence per share 1,127 · 0.1p Volume: 1,000,000."""
    vol = val = 0.0
    for m in re.finditer(rf"([\d][\d,]*(?:\.\d+)?)\s*({_PRICE_UNIT})\s+(?:volume\s*:?\s*)?"
                         rf"([\d][\d,]*(?:\.\d+)?)", region, re.I):
        price, qty = _to_float(m.group(1)), _to_float(m.group(3))
        if price is None or not qty:
            continue
        pounds = price / 100 if _unit_pence(m.group(2)) else price
        vol += qty
        val += pounds * qty
    return vol, val


def _rows_prefix(region: str) -> tuple[float, float]:
    """Filas 'unidad precio volumen' (divisa pegada al precio): GBP1.0348 718,013 · £0.76 132,000."""
    vol = val = 0.0
    for m in re.finditer(r"(£|gbp|gbx)\s*([\d][\d,]*(?:\.\d+)?)\s+(?:volume\s*:?\s*)?"
                         r"([\d][\d,]*(?:\.\d+)?)", region, re.I):
        price, qty = _to_float(m.group(2)), _to_float(m.group(3))
        if price is None or not qty:
            continue
        pounds = price / 100 if m.group(1).lower() == "gbx" else price
        vol += qty
        val += pounds * qty
    return vol, val


def _parse_price_volume(seg: str) -> tuple[float | None, float | None]:
    """(shares, precio en libras) desde la tabla precio/volumen, agregando filas (VWAP).

    Cubre las variantes de plantilla MAR vistas en el NSM (HTML de Word):
    estándar LSEG '<precio> GBP <vol> <total> GBP' (incl. multi-fila vía total), divisa
    pegada 'GBP1.0348 <vol>' / '£0.76 <vol>', peniques '60p'/'13.5 pence'/'4412 pence per
    share', volumen etiquetado 'Volume: <n>' y precio nulo ('Nil'/'GBP 0.00'). (None, None)
    si no casa (no afecta a los recuentos). A propósito quedan sin importe: texto libre
    ('price of 13.5 pence per share') y divisa extranjera (USD/ZAR de cotizaciones duales),
    porque convertirla a £ falsearía los agregados."""
    seg = _clean_money(seg)
    pm = re.search(r"Price\s*\(?s?\)?\s*(?:&|and)?\s*[Vv]olume|Exercise price|Price\s*[:&]",
                   seg, re.I)
    region = re.split(r"Aggregated", seg[pm.start():] if pm else seg, maxsplit=1, flags=re.I)[0]

    # 1) Estándar '<precio> GBP <vol> <total> GBP' (multi-fila correcto vía total)
    pence_std = "GBX" in region
    vol = val = 0.0
    for _p, qty, total in re.findall(
            r"([\d,]+(?:\.\d+)?)\s+GB[PX]\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s*GB[PX]",
            region, re.I):
        qf, tf = _to_float(qty), _to_float(total)
        if qf and tf:
            vol += qf
            val += tf
    if vol and val:
        return (round(vol, 4), round((val / vol) / (100 if pence_std else 1), 6))

    # 2) Filas con unidad (prefijo si la divisa va pegada al número; si no, sufijo)
    vol, val = (_rows_prefix(region) if re.search(r"(?:£|GBP|GBX)\d", region, re.I)
                else _rows_suffix(region))
    if vol and val:
        return (round(vol, 4), round(val / vol, 6))

    # 3) Precio nulo (ejercicios/concesiones sin coste): 'Nil <vol>' / 'GBP 0.00 <vol>'
    m = re.search(r"(?:nil|gbp\s*0\.0+|£\s*0\.0+|0\.0+\s*gb[px])\s+(?:volume\s*:?\s*)?"
                  r"([\d][\d,]*)", region, re.I)
    if m:
        qty = _to_float(m.group(1))
        if qty:
            return (round(qty, 4), 0.0)
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

    # Precio/volumen: sección 4 hasta la fecha/lugar (la unidad por fila decide £ vs peniques)
    pv_seg = re.split(r"Date of (?:the )?transaction|Place of (?:the )?transaction",
                      sec4, maxsplit=1, flags=re.I)[0]
    shares, price = _parse_price_volume(pv_seg)

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
