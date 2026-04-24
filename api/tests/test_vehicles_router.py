import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db


def _mock_db(fetch_return=None):
    db = AsyncMock()
    db.fetch.return_value = fetch_return if fetch_return is not None else []
    return db


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    app.dependency_overrides[get_db] = _dep


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    _override_db(_mock_db([]))  # default; individual tests replace as needed
    with patch("app.main.create_pool", new_callable=AsyncMock), \
         patch("app.main.close_pool", new_callable=AsyncMock):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/vehicles/years
# ---------------------------------------------------------------------------

class TestListYears:
    def test_returns_list_of_ints(self, client):
        _override_db(_mock_db([{"year": 2023}, {"year": 2022}, {"year": 2021}]))
        resp = client.get("/api/vehicles/years")
        assert resp.status_code == 200
        assert resp.json() == [2023, 2022, 2021]

    def test_empty_table_returns_empty_list(self, client):
        _override_db(_mock_db([]))
        resp = client.get("/api/vehicles/years")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/vehicles/makes
# ---------------------------------------------------------------------------

class TestListMakes:
    def test_returns_makes_for_year(self, client):
        _override_db(_mock_db([{"make_normalized": "Honda"}, {"make_normalized": "Toyota"}]))
        resp = client.get("/api/vehicles/makes", params={"year": 2020})
        assert resp.status_code == 200
        assert resp.json() == ["Honda", "Toyota"]

    def test_missing_year_returns_422(self, client):
        resp = client.get("/api/vehicles/makes")
        assert resp.status_code == 422

    def test_year_below_range_returns_422(self, client):
        resp = client.get("/api/vehicles/makes", params={"year": 1800})
        assert resp.status_code == 422

    def test_year_above_range_returns_422(self, client):
        resp = client.get("/api/vehicles/makes", params={"year": 2200})
        assert resp.status_code == 422

    def test_no_makes_for_year_returns_empty_list(self, client):
        _override_db(_mock_db([]))
        resp = client.get("/api/vehicles/makes", params={"year": 1999})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_passes_year_to_db(self, client):
        mock_db = _mock_db([{"make_normalized": "Ford"}])
        _override_db(mock_db)
        client.get("/api/vehicles/makes", params={"year": 2018})
        call_args = mock_db.fetch.call_args
        assert 2018 in call_args.args


# ---------------------------------------------------------------------------
# GET /api/vehicles/models
# ---------------------------------------------------------------------------

class TestListModels:
    def test_returns_models_for_year_and_make(self, client):
        _override_db(_mock_db([{"model_normalized": "Camry"}, {"model_normalized": "Corolla"}]))
        resp = client.get("/api/vehicles/models", params={"year": 2020, "make": "Toyota"})
        assert resp.status_code == 200
        assert resp.json() == ["Camry", "Corolla"]

    def test_missing_year_returns_422(self, client):
        resp = client.get("/api/vehicles/models", params={"make": "Toyota"})
        assert resp.status_code == 422

    def test_missing_make_returns_422(self, client):
        resp = client.get("/api/vehicles/models", params={"year": 2020})
        assert resp.status_code == 422

    def test_empty_make_returns_422(self, client):
        resp = client.get("/api/vehicles/models", params={"year": 2020, "make": ""})
        assert resp.status_code == 422

    def test_no_models_returns_empty_list(self, client):
        _override_db(_mock_db([]))
        resp = client.get("/api/vehicles/models", params={"year": 2020, "make": "Pontiac"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_passes_year_and_make_to_db(self, client):
        mock_db = _mock_db([{"model_normalized": "F-150"}])
        _override_db(mock_db)
        client.get("/api/vehicles/models", params={"year": 2019, "make": "Ford"})
        call_args = mock_db.fetch.call_args
        assert 2019 in call_args.args
        assert "Ford" in call_args.args
