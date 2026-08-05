def apply_discount(price: float, discount_pct: float) -> float:
    """Return price after applying a percentage discount (e.g. 0.10 = 10% off)."""
    return price - (discount_pct * price)


def final_price(discount_pct: float, price: float) -> float:
    """Compute the final price given a discount percentage and a base price."""
    return apply_discount(discount_pct, price)
