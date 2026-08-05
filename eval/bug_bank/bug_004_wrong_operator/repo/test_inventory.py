from inventory import total_value


def test_total_value_basic():
    assert total_value(10, 3) == 30


def test_total_value_zero_quantity():
    assert total_value(10, 0) == 0


def test_total_value_single_unit():
    assert total_value(7, 1) == 7
