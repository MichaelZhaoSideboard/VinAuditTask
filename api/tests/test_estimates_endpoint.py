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


def _make_rows(n: int, price: float, mileage=None):
    return [
        {
            "listing_price": price,
            "listing_mileage": mileage,
            "used": True,
            "dealer_city": "Springfield",
            "dealer_state": "IL",
        }
        for _ in range(n)
    ]


def _make_linear_rows(n: int, base_price: float, slope: float, base_mileage: float, step: float):
    rows = []
    for i in range(n):
        m = int(base_mileage + i * step)
        rows.append({
            "listing_price": base_price + slope * m,
            "listing_mileage": m,
            "used": True,
            "dealer_city": "Springfield",
            "dealer_state": "IL",
        })
    return rows


BASE_PARAMS = {"year": 2020, "make": "Toyota", "model": "Camry"}


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
# Validation / 422
# ---------------------------------------------------------------------------

class TestEstimateValidation:
    def test_missing_year_returns_422(self, client):
        resp = client.get("/api/estimates", params={"make": "Toyota", "model": "Camry"})
        assert resp.status_code == 422

    def test_missing_make_returns_422(self, client):
        resp = client.get("/api/estimates", params={"year": 2020, "model": "Camry"})
        assert resp.status_code == 422

    def test_missing_model_returns_422(self, client):
        resp = client.get("/api/estimates", params={"year": 2020, "make": "Toyota"})
        assert resp.status_code == 422

    def test_year_out_of_range_returns_422(self, client):
        resp = client.get("/api/estimates", params={"year": 1800, "make": "Toyota", "model": "Camry"})
        assert resp.status_code == 422

    def test_negative_mileage_returns_422(self, client):
        resp = client.get("/api/estimates", params={**BASE_PARAMS, "mileage": -1})
        assert resp.status_code == 422

    def test_mileage_above_500k_returns_422(self, client):
        resp = client.get("/api/estimates", params={**BASE_PARAMS, "mileage": 500_001})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 404 – not enough data
# ---------------------------------------------------------------------------

class TestEstimateNotFound:
    def test_fewer_than_5_rows_returns_404(self, client):
        _override_db(_mock_db(_make_rows(4, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.status_code == 404

    def test_zero_rows_returns_404(self, client):
        _override_db(_mock_db([]))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.status_code == 404

    def test_404_detail_mentions_vehicle(self, client):
        _override_db(_mock_db(_make_rows(3, 20000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert "2020" in resp.json()["detail"]
        assert "Toyota" in resp.json()["detail"]
        assert "Camry" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path – no mileage
# ---------------------------------------------------------------------------

class TestEstimateNoMileage:
    def test_returns_200(self, client):
        _override_db(_mock_db(_make_rows(10, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.status_code == 200

    def test_response_schema_fields_present(self, client):
        _override_db(_mock_db(_make_rows(10, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        body = resp.json()
        assert "estimated_price" in body
        assert "price_low" in body
        assert "price_high" in body
        assert "sample_count" in body
        assert "mileage_adjusted" in body
        assert "sample_listings" in body

    def test_sample_count_matches_db_rows(self, client):
        _override_db(_mock_db(_make_rows(12, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.json()["sample_count"] == 12

    def test_mileage_adjusted_is_false_without_mileage_param(self, client):
        _override_db(_mock_db(_make_rows(10, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.json()["mileage_adjusted"] is False

    def test_uniform_prices_all_same_estimate(self, client):
        _override_db(_mock_db(_make_rows(10, 30000.0)))
        body = client.get("/api/estimates", params=BASE_PARAMS).json()
        assert body["estimated_price"] == 30000
        assert body["price_low"] == 30000
        assert body["price_high"] == 30000

    def test_sample_listings_include_vehicle_info(self, client):
        _override_db(_mock_db(_make_rows(5, 20000.0)))
        body = client.get("/api/estimates", params=BASE_PARAMS).json()
        listing = body["sample_listings"][0]
        assert listing["year"] == 2020
        assert listing["make"] == "Toyota"
        assert listing["model"] == "Camry"
        assert listing["price"] == 20000


# ---------------------------------------------------------------------------
# Happy path – with mileage adjustment
# ---------------------------------------------------------------------------

class TestEstimateWithMileage:
    def test_mileage_adjusted_true_with_enough_paired_data(self, client):
        rows = _make_linear_rows(20, 40000.0, -0.10, 0.0, 5000.0)
        _override_db(_mock_db(rows))
        body = client.get("/api/estimates", params={**BASE_PARAMS, "mileage": 0}).json()
        assert body["mileage_adjusted"] is True

    def test_mileage_adjusted_false_with_no_mileage_data(self, client):
        _override_db(_mock_db(_make_rows(15, 25000.0, mileage=None)))
        body = client.get("/api/estimates", params={**BASE_PARAMS, "mileage": 50000}).json()
        assert body["mileage_adjusted"] is False

    def test_estimate_at_zero_miles_near_base_price(self, client):
        # price = 40000 - 0.10 * mileage; at 0 miles → ~40000
        rows = _make_linear_rows(20, 40000.0, -0.10, 0.0, 5000.0)
        _override_db(_mock_db(rows))
        body = client.get("/api/estimates", params={**BASE_PARAMS, "mileage": 0}).json()
        assert abs(body["estimated_price"] - 40000) < 100

    def test_mileage_param_is_optional(self, client):
        _override_db(_mock_db(_make_rows(10, 25000.0)))
        resp = client.get("/api/estimates", params=BASE_PARAMS)
        assert resp.status_code == 200

    def test_sample_listings_capped_at_100(self, client):
        rows = _make_rows(120, 25000.0)
        _override_db(_mock_db(rows))
        body = client.get("/api/estimates", params=BASE_PARAMS).json()
        assert len(body["sample_listings"]) <= 100
        assert body["sample_count"] == 120
