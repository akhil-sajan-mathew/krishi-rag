"""Redis answer cache and per-IP rate limit. Both fail open: if Redis is down, /ask still works."""

import hashlib
import json
import logging
import re
from functools import cache

import redis

from app.config import settings
from app.generate import SYSTEM

log = logging.getLogger("krishi.cache")
TTL_SECONDS = 7 * 24 * 3600


@cache
def client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)


def answer_key(question: str, mode: str) -> str:
    """Same question + same settings -> same key. Any setting that changes answers is included."""
    normalized = re.sub(r"\s+", " ", question.lower()).strip().rstrip("?.! ")
    parts = [
        normalized,
        mode,
        settings.chunk_config,
        str(settings.keyword_weight),
        str(settings.rerank_pool),
        settings.rerank_model,
        settings.llm_provider,
        settings.llm_model,
        hashlib.sha256(SYSTEM.encode()).hexdigest(),  # prompt changes invalidate old answers
    ]
    return "answer:" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def get_answer(key: str) -> dict | None:
    try:
        raw = client().get(key)
    except redis.RedisError as e:
        log.warning("cache read failed: %s", e)
        return None
    return json.loads(raw) if raw else None


def set_answer(key: str, result: dict) -> None:
    try:
        client().setex(key, TTL_SECONDS, json.dumps(result))
    except redis.RedisError as e:
        log.warning("cache write failed: %s", e)


def allow_request(ip: str) -> bool:
    """Fixed one-hour window per IP. Returns True when the request may proceed."""
    if settings.rate_limit_per_hour <= 0:
        return True
    key = f"ratelimit:{ip}"
    try:
        count = client().incr(key)
        if count == 1:
            client().expire(key, 3600)
    except redis.RedisError as e:
        # shortcut: fail open so a Redis outage doesn't take /ask down; the provider's
        # own spend limit is the backstop. Fail closed if abuse becomes a real problem.
        log.warning("rate limit check failed: %s", e)
        return True
    return count <= settings.rate_limit_per_hour


def ping() -> bool:
    try:
        return bool(client().ping())
    except redis.RedisError:
        return False
