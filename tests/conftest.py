import pytest
import redis

from app import cache


class FakeRedis:
    """The four Redis commands the app uses, in memory. TTLs are recorded, not enforced."""

    def __init__(self, down: bool = False):
        self.data: dict[str, object] = {}
        self.ttl: dict[str, int] = {}
        self.down = down

    def _check(self):
        if self.down:
            raise redis.ConnectionError("redis is down")

    def get(self, key):
        self._check()
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self._check()
        self.data[key], self.ttl[key] = value, ttl

    def incr(self, key):
        self._check()
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    def expire(self, key, ttl):
        self._check()
        self.ttl[key] = ttl

    def ping(self):
        self._check()
        return True


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache, "client", lambda: fake)
    return fake
