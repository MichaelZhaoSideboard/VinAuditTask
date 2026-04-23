import pytest
from app.estimation import _percentile, _linear_regression_slope, calculate_estimate


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_median_of_odd_list(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0

    def test_median_of_even_list(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5

    def test_0th_percentile_is_minimum(self):
        assert _percentile([10.0, 20.0, 30.0], 0) == 10.0

    def test_100th_percentile_is_maximum(self):
        assert _percentile([10.0, 20.0, 30.0], 100) == 30.0

    def test_single_element(self):
        assert _percentile([42.0], 25) == 42.0
        assert _percentile([42.0], 75) == 42.0

    def test_interpolates_between_values(self):
        # p=25 on [0, 100] → index 0.25, interpolates to 25.0
        assert _percentile([0.0, 100.0], 25) == 25.0


# ---------------------------------------------------------------------------
# _linear_regression_slope
# ---------------------------------------------------------------------------

class TestLinearRegressionSlope:
    def test_perfect_negative_slope(self):
        # price drops $1 per mile: y = 50000 - x
        xs = [0.0, 10000.0, 20000.0, 30000.0]
        ys = [50000.0, 40000.0, 30000.0, 20000.0]
        assert _linear_regression_slope(xs, ys) == pytest.approx(-1.0)

    def test_perfect_positive_slope(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [2.0, 4.0, 6.0, 8.0]
        assert _linear_regression_slope(xs, ys) == pytest.approx(2.0)

    def test_zero_slope_when_price_is_constant(self):
        xs = [10000.0, 20000.0, 30000.0]
        ys = [25000.0, 25000.0, 25000.0]
        assert _linear_regression_slope(xs, ys) == pytest.approx(0.0)

    def test_returns_none_when_all_mileages_identical(self):
        # denominator is zero — degenerate input
        xs = [50000.0, 50000.0, 50000.0]
        ys = [20000.0, 22000.0, 24000.0]
        assert _linear_regression_slope(xs, ys) is None


# ---------------------------------------------------------------------------
# calculate_estimate
# ---------------------------------------------------------------------------

def _make_listings(n: int, base_price: float, slope: float, base_mileage: float, step: float):
    """Generate n listings following price = base_price + slope * mileage."""
    prices, mileages = [], []
    for i in range(n):
        m = base_mileage + i * step
        prices.append(base_price + slope * m)
        mileages.append(m)
    return prices, mileages


class TestCalculateEstimate:
    # --- no mileage ---

    def test_no_mileage_returns_median(self):
        prices = [10000.0, 20000.0, 30000.0, 40000.0, 50000.0]
        est, low, high, adjusted = calculate_estimate(prices, [None] * 5, None)
        assert est == 30000
        assert adjusted is False

    def test_no_mileage_returns_correct_percentile_range(self):
        prices = [float(x) for x in range(1, 101)]  # 1..100
        _, low, high, _ = calculate_estimate(prices, [None] * 100, None)
        assert low == pytest.approx(25.75, abs=1)
        assert high == pytest.approx(75.25, abs=1)

    def test_no_mileage_rounds_to_int(self):
        prices = [10001.6, 10002.4, 10003.0]
        est, low, high, _ = calculate_estimate(prices, [None] * 3, None)
        assert isinstance(est, int)
        assert isinstance(low, int)
        assert isinstance(high, int)

    # --- mileage provided, enough paired data ---

    def test_mileage_adjustment_applied_with_enough_samples(self):
        # Perfect linear data: price = 40000 - 0.10 * mileage
        prices, mileages = _make_listings(20, 40000.0, -0.10, 0.0, 5000.0)
        # At 0 miles all adjusted prices collapse to 40000
        est, low, high, adjusted = calculate_estimate(prices, mileages, 0)
        assert adjusted is True
        assert est == 40000
        assert low == 40000
        assert high == 40000

    def test_mileage_adjustment_shifts_estimate_correctly(self):
        # price = 50000 - 0.20 * mileage; avg mileage = 47500
        # At target 0 miles, estimate should be ~50000
        prices, mileages = _make_listings(20, 50000.0, -0.20, 0.0, 5000.0)
        est, _, _, adjusted = calculate_estimate(prices, mileages, 0)
        assert adjusted is True
        assert est == pytest.approx(50000, abs=1)

    def test_mileage_adjusted_flag_is_true(self):
        prices, mileages = _make_listings(15, 30000.0, -0.05, 10000.0, 3000.0)
        _, _, _, adjusted = calculate_estimate(prices, mileages, 50000)
        assert adjusted is True

    # --- mileage provided but falls back to unadjusted ---

    def test_falls_back_when_fewer_than_10_paired_samples(self):
        prices = [20000.0, 25000.0, 30000.0, 35000.0, 40000.0]
        mileages = [10000.0, 20000.0, None, None, None]  # only 2 paired
        _, _, _, adjusted = calculate_estimate(prices, mileages, 30000)
        assert adjusted is False

    def test_falls_back_when_all_mileages_are_none(self):
        prices = [15000.0, 20000.0, 25000.0]
        mileages = [None, None, None]
        _, _, _, adjusted = calculate_estimate(prices, mileages, 30000)
        assert adjusted is False

    def test_falls_back_when_all_mileages_identical(self):
        # Regression slope is None — should fall back gracefully
        prices, mileages = _make_listings(15, 25000.0, 0.0, 50000.0, 0.0)
        _, _, _, adjusted = calculate_estimate(prices, mileages, 30000)
        assert adjusted is False

    def test_falls_back_when_target_mileage_is_none(self):
        prices, mileages = _make_listings(15, 30000.0, -0.10, 0.0, 5000.0)
        _, _, _, adjusted = calculate_estimate(prices, mileages, None)
        assert adjusted is False
