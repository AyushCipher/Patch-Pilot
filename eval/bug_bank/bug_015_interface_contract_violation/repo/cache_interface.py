class Cache:
    """A cache maps keys to values.

    Contract: get() MUST return None on a miss. Callers rely on this and
    do not (and should not have to) catch exceptions from get().
    """

    def get(self, key):
        raise NotImplementedError

    def set(self, key, value):
        raise NotImplementedError
