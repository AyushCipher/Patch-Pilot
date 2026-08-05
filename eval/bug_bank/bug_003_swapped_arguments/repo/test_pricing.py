from pricing import final_price


def test_final_price_ten_percent_off():
    assert final_price(0.10, 100) == 90


def test_final_price_no_discount():
    assert final_price(0.0, 50) == 50


def test_final_price_fifty_percent():
    assert final_price(0.5, 200) == 100
