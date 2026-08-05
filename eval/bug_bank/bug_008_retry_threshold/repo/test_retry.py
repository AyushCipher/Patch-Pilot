from retry import should_retry


def test_first_attempt_retries():
    assert should_retry(1) is True


def test_second_attempt_retries():
    assert should_retry(2) is True


def test_third_attempt_stops():
    assert should_retry(3) is False
