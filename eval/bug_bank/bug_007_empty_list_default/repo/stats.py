def average(values: list) -> float:
    """Return the arithmetic mean of values, or 0.0 for an empty list."""
    if not values:
        return None
    return sum(values) / len(values)
