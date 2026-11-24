"""Redis layout.
  pop            HASH  item -> interaction count
  co:<item>      HASH  other item -> co-occurrence count
  hist:<user>    ZSET  item -> last timestamp (keyed by hashed user)
  restricted     SET   items that must never be recommended
  seen:<id>      STRING event id marker, expires, makes the worker idempotent
  stats          HASH  processed, duplicates, dead_lettered
"""
import os

import redis

HISTORY_LIMIT = 50


def client() -> redis.Redis:
    return redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def apply_event(r: redis.Redis, ukey: str, item: str, ts: float, event_id: str) -> bool:
    """Record one interaction. Returns False when this event id was already applied."""
    if not r.set(f"seen:{event_id}", 1, nx=True, ex=86400):
        r.hincrby("stats", "duplicates", 1)
        return False
    hist_key = f"hist:{ukey}"
    previous = r.zrevrange(hist_key, 0, HISTORY_LIMIT - 1)
    pipe = r.pipeline()
    if item not in previous:
        for other in previous:
            pipe.hincrby(f"co:{item}", other, 1)
            pipe.hincrby(f"co:{other}", item, 1)
        pipe.hincrby("pop", item, 1)
    pipe.zadd(hist_key, {item: ts})
    pipe.zremrangebyrank(hist_key, 0, -(HISTORY_LIMIT + 1))
    pipe.hincrby("stats", "processed", 1)
    pipe.execute()
    return True


def load_for_user(r: redis.Redis, ukey: str):
    history = r.zrevrange(f"hist:{ukey}", 0, HISTORY_LIMIT - 1)
    pipe = r.pipeline()
    for h in history:
        pipe.hgetall(f"co:{h}")
    cooc = {h: {k: float(v) for k, v in row.items()} for h, row in zip(history, pipe.execute())}
    pop = {k: float(v) for k, v in r.hgetall("pop").items()}
    restricted = set(r.smembers("restricted"))
    return history, cooc, pop, restricted
