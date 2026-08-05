from convert import celsius_to_fahrenheit


def format_report(celsius_temp: float) -> str:
    """Return a human-readable report showing the Fahrenheit equivalent."""
    fahrenheit = celsius_temp * 9 / 5
    return f"{fahrenheit:.1f}F"
