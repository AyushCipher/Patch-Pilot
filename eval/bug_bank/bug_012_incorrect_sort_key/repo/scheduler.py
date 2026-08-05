from records import sort_key


def schedule(records: list) -> list:
    """Order records for scheduling using the shared sort_key."""
    return sorted(records, key=sort_key)
