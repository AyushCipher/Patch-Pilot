from cache_interface import Cache


class MemoryCache(Cache):
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data[key]

    def set(self, key, value):
        self._data[key] = value
