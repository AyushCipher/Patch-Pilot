from grades import is_passing


def test_passing_at_threshold():
    assert is_passing(60) is True


def test_passing_above_threshold():
    assert is_passing(75) is True


def test_failing_below_threshold():
    assert is_passing(59) is False
