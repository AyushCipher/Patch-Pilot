from counter import RunningTotal


def compute_invoice_totals(order_batches: list) -> list:
    """Given a list of batches (each a list of order amounts), return the
    total for each batch independently - batches must not leak into
    each other's totals."""
    counter = RunningTotal()
    results = []
    for batch in order_batches:
        counter.reset()
        for amount in batch:
            counter.add(amount)
        results.append(counter.total)
    return results
