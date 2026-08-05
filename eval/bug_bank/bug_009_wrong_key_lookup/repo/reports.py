def active_emails(users) -> list:
    """Return the emails of active users, using each User's dict representation."""
    result = []
    for u in users:
        d = u.to_dict()
        if d["is_active"]:
            result.append(d["email"])
    return result
