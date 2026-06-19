"""Parsers de insiders (XML Form 4 + TSV DERA) — deterministas, sin red."""
from app.ingest.insider_mappers import (
    code_to_action,
    parse_form4_xml,
    transactions_from_dera,
)

FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001214156</rptOwnerCik>
      <rptOwnerName>COOK TIMOTHY D</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-05-01</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100000</value></transactionShares>
        <transactionPricePerShare><value>180.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>3280000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-05-02</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>P</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>181.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeHolding>
      <securityTitle><value>Common Stock</value></securityTitle>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>1</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeHolding>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Restricted Stock Unit</value></securityTitle>
      <transactionDate><value>2024-04-01</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>M</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""


def test_code_to_action():
    assert code_to_action("P") == "buy"
    assert code_to_action("S") == "sell"
    assert code_to_action("M") == "exercise"
    assert code_to_action("A") == "grant"
    assert code_to_action("F") == "tax"
    assert code_to_action("Z") == "other"   # desconocido
    assert code_to_action(None) == "other"
    assert code_to_action("p") == "buy"      # case-insensitive


def test_parse_form4_basic():
    txns = parse_form4_xml(FORM4_XML, accession="0000320193-24-000001")
    # 2 no-derivadas (la "holding" sin transacción se ignora) + 1 derivada
    assert len(txns) == 3

    sale = txns[0]
    assert sale["symbol"] == "AAPL"          # de issuerTradingSymbol
    assert sale["cik"] == "0000320193"
    assert sale["filer"] == "COOK TIMOTHY D"
    assert sale["relationship"] == "Officer (Chief Executive Officer)"
    assert sale["code"] == "S" and sale["action"] == "sell"
    assert sale["shares"] == 100000.0 and sale["price"] == 180.5
    assert sale["shares_after"] == 3280000.0
    assert sale["ownership"] == "D" and sale["is_derivative"] is False
    assert sale["accession"] == "0000320193-24-000001"

    buy = txns[1]
    assert buy["code"] == "P" and buy["action"] == "buy"
    assert buy["shares"] == 500.0 and buy["price"] == 181.0

    deriv = txns[2]
    assert deriv["is_derivative"] is True
    assert deriv["code"] == "M" and deriv["action"] == "exercise"


def test_parse_form4_symbol_override_and_bad_xml():
    txns = parse_form4_xml(FORM4_XML, symbol="aapl")
    assert all(t["symbol"] == "AAPL" for t in txns)   # se normaliza a mayúsculas
    assert parse_form4_xml("<not valid") == []         # XML roto → [] (no rompe el lote)


DERA_SUB = [
    {"ACCESSION_NUMBER": "acc1", "DOCUMENT_TYPE": "4",
     "ISSUERTRADINGSYMBOL": "AAPL", "ISSUERCIK": "320193"},
    {"ACCESSION_NUMBER": "acc2", "DOCUMENT_TYPE": "4",
     "ISSUERTRADINGSYMBOL": "ZZZZ", "ISSUERCIK": "999"},
]
DERA_OWNERS = [
    {"ACCESSION_NUMBER": "acc1", "RPTOWNERNAME": "COOK TIMOTHY D",
     "DIRECTOR": "0", "OFFICER": "1", "OFFICER_TITLE": "CEO", "TENPERCENTOWNER": "0"},
    {"ACCESSION_NUMBER": "acc2", "RPTOWNERNAME": "DOE JANE", "TENPERCENTOWNER": "1"},
]
DERA_NONDERIV = [
    {"ACCESSION_NUMBER": "acc1", "TRANS_DATE": "01-MAY-2024", "TRANS_CODE": "P",
     "TRANS_SHARES": "500", "TRANS_PRICEPERSHARE": "180.5", "TRANS_ACQUIRED_DISP_CD": "A",
     "SHRS_OWND_FOLWNG_TRANS": "1000", "DIRECT_INDIRECT_OWNERSHIP": "D"},
    {"ACCESSION_NUMBER": "acc2", "TRANS_DATE": "02-MAY-2024", "TRANS_CODE": "S",
     "TRANS_SHARES": "10", "TRANS_PRICEPERSHARE": "1.0", "TRANS_ACQUIRED_DISP_CD": "D"},
]


def test_transactions_from_dera_filters_universe():
    out = transactions_from_dera(DERA_SUB, DERA_OWNERS, DERA_NONDERIV, [], symbols={"AAPL"})
    assert len(out) == 1
    t = out[0]
    assert t["symbol"] == "AAPL" and t["cik"] == "320193"
    assert t["filer"] == "COOK TIMOTHY D"
    assert t["relationship"] == "Officer (CEO)"
    assert t["txn_date"] == "2024-05-01"          # 01-MAY-2024 → ISO
    assert t["code"] == "P" and t["action"] == "buy"
    assert t["shares"] == 500.0 and t["price"] == 180.5
    assert t["ownership"] == "D" and t["is_derivative"] is False


def test_transactions_from_dera_no_filter_includes_all():
    out = transactions_from_dera(DERA_SUB, DERA_OWNERS, DERA_NONDERIV, [])
    assert {t["symbol"] for t in out} == {"AAPL", "ZZZZ"}
    jane = next(t for t in out if t["symbol"] == "ZZZZ")
    assert jane["relationship"] == "10% Owner"
