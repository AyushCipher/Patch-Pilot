def can_access(is_active: bool, is_verified: bool) -> bool:
    """A user can access the system only if their account is both active and verified."""
    return is_active or is_verified
