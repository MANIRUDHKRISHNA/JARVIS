"""Memory storage abstraction."""


class Memory:
    """Minimal memory container."""

    def __init__(self):
        self.data = {}

    def store(self, key: str, value):
        self.data[key] = value

    def get(self, key: str, default=None):
        return self.data.get(key, default)
