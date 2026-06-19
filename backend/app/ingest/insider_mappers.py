"""Parsers PUROS de la actividad de insiders (sin red) → dicts normalizados.

Convierten las dos fuentes oficiales de la SEC al mismo formato de transacción:

  1. XML de Form 3/4/5 ("ownershipDocument")  → parse_form4_xml()
  2. Datasets trimestrales DERA "Form 345" (TSV) → transactions_from_dera()

Formato normalizado (dict) que produce cada transacción:
    symbol, cik, accession, filer, relationship, txn_date (ISO), code, action,
    shares, price, shares_after, ownership (D|I), is_derivative (bool), url

El importe ($M) y los agregados por ventana se calculan después en
`services/insider_metrics.py`. Aquí solo se extrae y normaliza el dato crudo.

Estos parsers son deterministas y se testean sin tocar la red (ver tests/).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

# Código de transacción SEC (Form 4) → acción legible.
# P/S son las de MERCADO ABIERTO (la señal real); el resto es ruido de compensación.
CODE_ACTIONS: dict[str, str] = {
    "P": "buy",         # compra en mercado abierto
    "S": "sell",        # venta en mercado abierto
    "A": "grant",       # concesión/premio (RSU, etc.)
    "F": "tax",         # acciones entregadas para pagar impuestos/precio de ejercicio
    "M": "exercise",    # ejercicio/conversión de derivado adquisitivo
    "X": "exercise",    # ejercicio de opción in-the-money
    "C": "conversion",  # conversión de valor derivado
    "G": "gift",        # donación
    "D": "disposition", # disposición a favor del emisor
    "W": "other",       # adquisición/disposición por testamento o ley
    "J": "other",       # otra (explicada en footnote)
}

OPEN_MARKET = {"P", "S"}  # las únicas que cuentan para la señal compra/venta


def code_to_action(code: str | None) -> str:
    return CODE_ACTIONS.get((code or "").strip().upper(), "other")


# --------------------------------------------------------------------------- #
# 1) XML de Form 4 (ownershipDocument)
# --------------------------------------------------------------------------- #

def _text(node: ET.Element | None) -> str | None:
    """Texto de un nodo, desenvolviendo el wrapper <value> típico del esquema."""
    if node is None:
        return None
    inner = node.find("value")
    target = inner if inner is not None else node
    txt = (target.text or "").strip() if target is not None else ""
    return txt or None


def _num(node: ET.Element | None) -> float | None:
    txt = _text(node)
    if txt is None:
        return None
    try:
        return float(txt.replace(",", ""))
    except ValueError:
        return None


def _relationship(rel: ET.Element | None) -> str | None:
    """Construye el rol legible a partir de los flags isDirector/isOfficer/…"""
    if rel is None:
        return None
    parts: list[str] = []
    if (_text(rel.find("isDirector")) or "0") in ("1", "true"):
        parts.append("Director")
    if (_text(rel.find("isOfficer")) or "0") in ("1", "true"):
        title = _text(rel.find("officerTitle"))
        parts.append(f"Officer ({title})" if title else "Officer")
    if (_text(rel.find("isTenPercentOwner")) or "0") in ("1", "true"):
        parts.append("10% Owner")
    if (_text(rel.find("isOther")) or "0") in ("1", "true"):
        other = _text(rel.find("otherText"))
        parts.append(other or "Other")
    return ", ".join(parts) or None


def _transactions_from_table(table: ET.Element | None, tag: str, *, derivative: bool,
                             base: dict) -> list[dict]:
    if table is None:
        return []
    out: list[dict] = []
    for tx in table.findall(tag):
        coding = tx.find("transactionCoding")
        amounts = tx.find("transactionAmounts")
        if coding is None or amounts is None:
            continue  # holding (sin transacción) → fuera
        code = _text(coding.find("transactionCode"))
        post = tx.find("postTransactionAmounts")
        nature = tx.find("ownershipNature")
        out.append({
            **base,
            "txn_date": _text(tx.find("transactionDate")),
            "code": code,
            "action": code_to_action(code),
            "shares": _num(amounts.find("transactionShares")),
            "price": _num(amounts.find("transactionPricePerShare")),
            "acquired_disposed": _text(amounts.find("transactionAcquiredDisposedCode")),
            "shares_after": _num(post.find("sharesOwnedFollowingTransaction")) if post is not None else None,
            "ownership": _text(nature.find("directOrIndirectOwnership")) if nature is not None else None,
            "is_derivative": derivative,
        })
    return out


def parse_form4_xml(xml_text: str, *, symbol: str | None = None,
                    accession: str | None = None, url: str | None = None) -> list[dict]:
    """Parsea un ownershipDocument (Form 3/4/5) → lista de transacciones normalizadas.

    Devuelve [] ante XML inválido (no debe abortar el lote de ingesta).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    issuer = root.find("issuer")
    issuer_symbol = _text(issuer.find("issuerTradingSymbol")) if issuer is not None else None
    issuer_cik = _text(issuer.find("issuerCik")) if issuer is not None else None

    owner = root.find("reportingOwner")
    filer = None
    relationship = None
    if owner is not None:
        oid = owner.find("reportingOwnerId")
        filer = _text(oid.find("rptOwnerName")) if oid is not None else None
        relationship = _relationship(owner.find("reportingOwnerRelationship"))

    base = {
        "symbol": (symbol or issuer_symbol or "").upper() or None,
        "cik": issuer_cik,
        "accession": accession,
        "filer": filer or "Unknown",
        "relationship": relationship,
        "url": url,
    }

    txns = _transactions_from_table(
        root.find("nonDerivativeTable"), "nonDerivativeTransaction", derivative=False, base=base)
    txns += _transactions_from_table(
        root.find("derivativeTable"), "derivativeTransaction", derivative=True, base=base)
    return txns


# --------------------------------------------------------------------------- #
# 2) Datasets trimestrales DERA "Form 345" (TSV ya parseado a dicts)
#    Columnas según el readme oficial:
#    https://www.sec.gov/files/insider_transactions_readme.pdf
# --------------------------------------------------------------------------- #

def _dera_relationship(owner_row: dict) -> str | None:
    parts: list[str] = []
    if str(owner_row.get("DIRECTOR", "")).strip() in ("1", "true", "Y"):
        parts.append("Director")
    if str(owner_row.get("OFFICER", "")).strip() in ("1", "true", "Y"):
        title = (owner_row.get("OFFICER_TITLE") or "").strip()
        parts.append(f"Officer ({title})" if title else "Officer")
    if str(owner_row.get("TENPERCENTOWNER", "")).strip() in ("1", "true", "Y"):
        parts.append("10% Owner")
    if str(owner_row.get("OTHER", "")).strip() in ("1", "true", "Y"):
        parts.append((owner_row.get("OTHER_TEXT") or "Other").strip())
    return ", ".join(parts) or None


def _dera_date(raw: str | None) -> str | None:
    """DERA trae fechas como 'DD-MON-YYYY' (p. ej. 01-MAY-2024) → ISO yyyy-mm-dd."""
    if not raw:
        return None
    raw = raw.strip()
    months = {m: f"{i:02d}" for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
    parts = raw.replace("/", "-").split("-")
    try:
        if len(parts) == 3 and parts[1].upper() in months:      # 01-MAY-2024
            d, mon, y = parts
            return f"{y}-{months[mon.upper()]}-{int(d):02d}"
        if len(parts) == 3 and len(parts[0]) == 4:              # 2024-05-01
            return raw[:10]
    except (ValueError, KeyError):
        return None
    return None


def _dera_num(raw: str | None) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return None


def transactions_from_dera(submissions: list[dict], owners: list[dict],
                           nonderiv: list[dict], deriv: list[dict],
                           symbols: set[str] | None = None) -> list[dict]:
    """Une las tablas TSV de un trimestre DERA por ACCESSION_NUMBER → transacciones.

    `symbols` (opcional): si se pasa, solo se devuelven filings cuyo ticker esté en
    el universo (evita ingerir las ~500k operaciones de un trimestre entero).
    """
    sub_by_acc: dict[str, dict] = {}
    for s in submissions:
        if str(s.get("DOCUMENT_TYPE", "")).strip().rstrip("/A") not in ("3", "4", "5"):
            continue
        sym = (s.get("ISSUERTRADINGSYMBOL") or "").strip().upper()
        if symbols is not None and sym not in symbols:
            continue
        sub_by_acc[s["ACCESSION_NUMBER"]] = {
            "symbol": sym or None,
            "cik": (s.get("ISSUERCIK") or "").strip() or None,
        }

    owner_by_acc: dict[str, dict] = {o["ACCESSION_NUMBER"]: o for o in owners}

    def build(rows: list[dict], *, derivative: bool) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            acc = r.get("ACCESSION_NUMBER")
            sub = sub_by_acc.get(acc)
            if sub is None:
                continue
            owner = owner_by_acc.get(acc, {})
            code = (r.get("TRANS_CODE") or "").strip() or None
            out.append({
                "symbol": sub["symbol"],
                "cik": sub["cik"],
                "accession": acc,
                "filer": (owner.get("RPTOWNERNAME") or "Unknown").strip(),
                "relationship": _dera_relationship(owner),
                "txn_date": _dera_date(r.get("TRANS_DATE")),
                "code": code,
                "action": code_to_action(code),
                "shares": _dera_num(r.get("TRANS_SHARES")),
                "price": _dera_num(r.get("TRANS_PRICEPERSHARE")),
                "acquired_disposed": (r.get("TRANS_ACQUIRED_DISP_CD") or "").strip() or None,
                "shares_after": _dera_num(r.get("SHRS_OWND_FOLWNG_TRANS")),
                "ownership": (r.get("DIRECT_INDIRECT_OWNERSHIP") or "").strip() or None,
                "is_derivative": derivative,
                "url": None,
            })
        return out

    return build(nonderiv, derivative=False) + build(deriv, derivative=True)
