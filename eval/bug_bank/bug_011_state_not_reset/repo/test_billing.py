from billing import compute_invoice_totals


def test_independent_batches():
    batches = [[10, 20], [5], [100, 100, 100]]
    assert compute_invoice_totals(batches) == [30, 5, 300]


def test_single_batch():
    assert compute_invoice_totals([[1, 2, 3]]) == [6]
