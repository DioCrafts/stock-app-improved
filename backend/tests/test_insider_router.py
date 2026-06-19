"""Endpoint /companies/{ticker}/insiders — validación + forma de respuesta (sin red)."""
from fastapi.testclient import TestClient

from app.main import app
from app.models.insider import InsiderSummary, InsiderTransaction, InsiderWindow
from app.services import insider_service

client = TestClient(app)


def test_insiders_path_rejects_invalid():
    for bad in ["AAPL@", "AA PL", "TICKERWAYTOOLONGFORTHELIMIT"]:
        assert client.get(f"/companies/{bad}/insiders").status_code == 422, bad


def test_insiders_returns_bundle(monkeypatch):
    fixture = InsiderSummary(
        ticker="AAPL", cik="0000320193", currency="USD", updated="2024-06-01T00:00:00",
        windows=[InsiderWindow(days=180, buys=3, sells=1, netValue=8.0, cluster=True)],
        transactions=[InsiderTransaction(filer="COOK TIMOTHY D", relationship="Officer (CEO)",
                                         date="2024-05-02", code="P", action="buy",
                                         shares=500, price=181.0, value=0.09)],
    )
    monkeypatch.setattr(insider_service, "get_insider_summary", lambda *a, **k: fixture)
    r = client.get("/companies/AAPL/insiders")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL" and body["currency"] == "USD"
    assert body["windows"][0]["cluster"] is True
    assert body["transactions"][0]["action"] == "buy"


def test_insiders_empty_for_non_us(monkeypatch):
    # Un ticker no-US (sin CIK) devuelve bundle vacío con 200, no error.
    monkeypatch.setattr(insider_service, "get_insider_summary",
                        lambda *a, **k: InsiderSummary(ticker="HSBA.L", currency=None))
    r = client.get("/companies/HSBA.L/insiders")
    assert r.status_code == 200
    assert r.json()["windows"] == [] and r.json()["transactions"] == []
