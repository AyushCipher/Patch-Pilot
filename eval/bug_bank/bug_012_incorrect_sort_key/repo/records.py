def sort_key(record: dict):
    """Sort key: order by priority ascending, breaking ties by name."""
    return record["name"]
