"""Simple in-memory storage for the assistant."""


class MemoryStore:
    """Basic dictionary-backed memory store."""

    def __init__(self):
        self._data = {}

    def set(self, key: str, value):
        self._data[key] = value

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def clear(self):
        self._data.clear()
