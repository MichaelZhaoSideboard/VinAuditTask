import pytest
from app.routers.estimates import _clean_mileage, _MILEAGE_MAX


class TestCleanMileage:
    def test_none_returns_none(self):
        assert _clean_mileage(None) is None

    def test_zero_returns_none(self):
        assert _clean_mileage(0) is None

    def test_over_limit_returns_none(self):
        assert _clean_mileage(_MILEAGE_MAX + 1) is None

    def test_exactly_at_limit_is_kept(self):
        assert _clean_mileage(_MILEAGE_MAX) == float(_MILEAGE_MAX)

    def test_normal_mileage_is_kept(self):
        assert _clean_mileage(45000) == 45000.0

    def test_low_mileage_is_kept(self):
        assert _clean_mileage(1) == 1.0

    def test_obvious_data_error_excluded(self):
        assert _clean_mileage(2_455_410) is None
