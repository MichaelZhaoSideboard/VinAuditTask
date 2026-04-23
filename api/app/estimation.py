from statistics import median


def _percentile(sorted_data: list[float], p: int) -> float:
    n = len(sorted_data)
    idx = (p / 100) * (n - 1)
    lo = int(idx)
    hi = lo + 1
    frac = idx - lo
    if hi >= n:
        return sorted_data[lo]
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def _linear_regression_slope(xs: list[float], ys: list[float]) -> float | None:
    """Returns the slope β of price ~ mileage, or None if degenerate."""
    n = len(xs)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return None
    return numerator / denominator


# Minimum paired samples needed to apply mileage regression
_MIN_REGRESSION_SAMPLES = 10


def calculate_estimate(
    prices: list[float],
    mileages: list[float | None],
    target_mileage: int | None,
) -> tuple[int, int, int, bool]:
    """
    Returns (estimated_price, price_low, price_high, mileage_adjusted).

    If target_mileage is given and enough paired data exists, adjusts all prices
    to the target mileage via linear regression before computing percentiles.
    """
    mileage_adjusted = False

    if target_mileage is not None:
        paired = [(p, m) for p, m in zip(prices, mileages) if m is not None]
        if len(paired) >= _MIN_REGRESSION_SAMPLES:
            xs = [m for _, m in paired]
            ys = [p for p, _ in paired]
            slope = _linear_regression_slope(xs, ys)
            if slope is not None:
                adjusted = sorted(p - slope * (m - target_mileage) for p, m in paired)
                mileage_adjusted = True
                return (
                    round(median(adjusted)),
                    round(_percentile(adjusted, 25)),
                    round(_percentile(adjusted, 75)),
                    True,
                )

    sorted_prices = sorted(prices)
    return (
        round(median(sorted_prices)),
        round(_percentile(sorted_prices, 25)),
        round(_percentile(sorted_prices, 75)),
        False,
    )
