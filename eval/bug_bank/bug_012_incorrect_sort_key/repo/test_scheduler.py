from scheduler import schedule


def test_sorts_by_priority_then_name():
    records = [
        {"name": "zeta", "priority": 1},
        {"name": "alpha", "priority": 2},
        {"name": "beta", "priority": 1},
    ]
    result = schedule(records)
    assert [r["name"] for r in result] == ["beta", "zeta", "alpha"]


def test_single_record():
    records = [{"name": "only", "priority": 5}]
    assert schedule(records) == records
