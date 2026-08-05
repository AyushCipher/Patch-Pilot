from weather import format_report


def test_freezing():
    assert format_report(0) == "32.0F"


def test_boiling():
    assert format_report(100) == "212.0F"


def test_body_temp():
    assert format_report(37) == "98.6F"
