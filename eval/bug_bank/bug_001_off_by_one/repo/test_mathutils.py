from mathutils import sum_first_n


def test_sum_first_n_five():
    assert sum_first_n(5) == 15


def test_sum_first_n_one():
    assert sum_first_n(1) == 1


def test_sum_first_n_ten():
    assert sum_first_n(10) == 55
