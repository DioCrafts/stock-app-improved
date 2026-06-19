"""Parser de notificaciones PDMR del FCA NSM (UK) — determinista, sin red.

Las fixtures replican la plantilla estándar MAR (Reglamento UE 2016/523) tal como
aparece en los documentos reales del NSM (HTML exportado de Word).
"""
from app.ingest.nsm_mappers import (
    nature_to_action,
    normalize_company_name,
    parse_nsm_document,
)
from app.services.insider_metrics import summarize, to_models

# Compra en libras (GBP), con tabla precio/volumen de una fila.
DOC_BUY = """<html><head><style>td{border:1px solid}</style></head><body>
<p>RNS Number : 1234X Acme Plc 19 June 2026</p>
<p>1 Details of the natural / legal person a) Full name: Jane Director</p>
<p>2 Reason for the notification a) Position / status: Director b) Job title / function: CFO</p>
<p>3 Details of the issuer a) Legal entity name: Acme Group PLC b) LEI code: 213800ABCDEFGHIJKL12</p>
<p>4 Details of the transaction(s) a) Description of the security: Ordinary shares
b) Security identification code: GB00B1234567
c) Description of the nature of the transaction: Acquisition of Ordinary Shares
d) Currency: GBP - British Pound
e) Price &amp; volume: Price Volume Total 5.00 GBP 10,000.00 50,000.00 GBP Total 50,000.00 GBP
f) Date of transaction: 18 June 2026 g) Place of transaction: XLON</p>
</body></html>"""

# Venta en peniques (GBX) → debe convertirse a libras (÷100). Fecha dd/mm/yyyy.
DOC_SELL_PENCE = """<html><body>
<p>1 Details of the person discharging managerial responsibilities a) Name John Smith</p>
<p>2 Reason for the notification a) Position/status Director</p>
<p>3 Details of the issuer a) Name Beta PLC b) LEI 213800ZZ000000000099</p>
<p>4 Details of the transaction(s) a) Identification code GB00B7654321
b) Nature of the transaction Disposal of shares
d) Currency: GBX - Pence
e) Price &amp; volume: Price Volume Total 500.00 GBX 2,000.00 1,000,000.00 GBX Total 1,000,000.00 GBX
f) Date of the transaction: 17/06/2026</p>
</body></html>"""


def test_parse_buy_gbp():
    t = parse_nsm_document(DOC_BUY, symbol="ACME.L", company="Acme Group PLC",
                           lei="213800ABCDEFGHIJKL12", accession="abc")[0]
    assert t["symbol"] == "ACME.L"
    assert t["filer"] == "Jane Director"
    assert t["relationship"] == "Director, CFO"
    assert t["txn_date"] == "2026-06-18"
    assert t["code"] == "P" and t["action"] == "buy"
    assert t["shares"] == 10000.0 and t["price"] == 5.0
    assert t["isin"] == "GB00B1234567"
    assert t["currency"] == "GBP" and t["is_derivative"] is False
    assert t["accession"] == "abc"


def test_parse_sell_pence_to_pounds():
    t = parse_nsm_document(DOC_SELL_PENCE, symbol="BETA.L")[0]
    assert t["filer"] == "John Smith"
    assert t["code"] == "S" and t["action"] == "sell"
    assert t["txn_date"] == "2026-06-17"           # dd/mm/yyyy → ISO
    assert t["shares"] == 2000.0
    assert t["price"] == 5.0                        # 500 peniques ÷ 100 → £5.00
    assert t["isin"] == "GB00B7654321"


def test_parse_garbage_returns_empty():
    assert parse_nsm_document("<html><body>nothing here</body></html>") == []


def test_normalize_company_name():
    f = normalize_company_name
    assert f("WIZZ AIR HOLDINGS PLC") == f("Wizz Air Holdings Plc") == "WIZZAIR"
    assert f("S & U PLC") == "SANDU"
    assert f("United Utilities Group plc") == "UNITEDUTILITIES"


def test_nature_mapping():
    assert nature_to_action("Acquisition of Ordinary Shares") == ("buy", "P")
    assert nature_to_action("Disposal of shares") == ("sell", "S")
    assert nature_to_action("Option exercise and hold") == ("exercise", "M")
    assert nature_to_action("Vesting of conditional award") == ("grant", "A")
    assert nature_to_action("Sale of sufficient shares to cover tax") == ("tax", "F")


def test_parse_feeds_metrics():
    # Una compra parseada debe contar como 1 compra de mercado abierto en las métricas.
    txns = parse_nsm_document(DOC_BUY, symbol="ACME.L")
    w = next(x for x in summarize(txns, as_of=__import__("datetime").date(2026, 6, 30)) if x.days == 90)
    assert w.buys == 1 and w.sells == 0
    assert w.buyValue == 0.05                        # 10.000 × £5 / 1e6 = 0,05 £M
    models = to_models(txns)
    assert models[0].action == "buy" and models[0].value == 0.05
