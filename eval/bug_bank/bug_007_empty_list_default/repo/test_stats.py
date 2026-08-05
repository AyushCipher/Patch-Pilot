from stats import average


def test_average_basic():
    assert average([1, 2, 3]) == 2


def test_average_empty():
    assert average([]) == 0.0


def test_average_single():
    assert average([5]) == 5
