"""Tests de validación de entradas en los routers (M1)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ticker_path_rejects_invalid():
    # caracteres no permitidos o longitud excesiva → 422 (antes de tocar yfinance)
    for bad in ["AAPL@", "AA_PL", "AA PL", "TICKERWAYTOOLONGFORTHELIMIT"]:
        assert client.get(f"/companies/{bad}").status_code == 422, bad
        assert client.get(f"/companies/{bad}/prices").status_code == 422, bad
        assert client.get(f"/companies/{bad}/financials").status_code == 422, bad


def test_ticker_path_accepts_valid_shape():
    # forma válida → NO 422 (200 si está en snapshot, 404 si no)
    for good in ["AAPL", "BRK-B", "SHOP.TO"]:
        assert client.get(f"/companies/{good}").status_code != 422, good
