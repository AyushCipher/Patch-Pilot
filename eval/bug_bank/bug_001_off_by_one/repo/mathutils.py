def sum_first_n(n: int) -> int:
    """Return the sum of the integers 1..n inclusive."""
    total = 0
    for i in range(1, n):
        total += i
    return total
