from currency_utils import round_currency


def compute_total(item_prices: list) -> float:
    """Sum item prices and round only once, at the end, so rounding error
    does not accumulate across many items."""
    total = 0.0
    for price in item_prices:
        total += round_currency(price)
    return round_currency(total)
