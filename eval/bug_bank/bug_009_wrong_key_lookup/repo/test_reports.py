from models import User
from reports import active_emails


def test_active_emails_filters_inactive():
    users = [
        User(1, "a@example.com", True),
        User(2, "b@example.com", False),
        User(3, "c@example.com", True),
    ]
    assert active_emails(users) == ["a@example.com", "c@example.com"]


def test_active_emails_empty_when_none_active():
    users = [User(1, "a@example.com", False)]
    assert active_emails(users) == []
