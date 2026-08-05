from checkout import compute_total


def test_many_small_items_round_correctly():
    prices = [0.111] * 9
    assert compute_total(prices) == 1.00


def test_two_items_accumulate_correctly():
    prices = [1.994, 1.994]
    assert compute_total(prices) == 3.99
