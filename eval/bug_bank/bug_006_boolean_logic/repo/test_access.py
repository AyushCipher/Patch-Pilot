from access import can_access


def test_active_and_verified():
    assert can_access(True, True) is True


def test_active_not_verified():
    assert can_access(True, False) is False


def test_verified_not_active():
    assert can_access(False, True) is False


def test_neither():
    assert can_access(False, False) is False
