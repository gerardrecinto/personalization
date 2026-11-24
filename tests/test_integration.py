"""End to end against a running stack (docker compose, or kind through a port-forward)."""
import os
import subprocess
import time
import uuid

import httpx
import pytest

API = os.environ.get("API_URL", "http://localhost:8000")
COMPOSE = os.environ.get("STACK") == "compose"
c = httpx.Client(base_url=API, timeout=15)


def wait_until(fn, timeout=60, msg="condition"):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
        except httpx.TransportError:  # API still starting or restarting
            v = None
        if v:
            return v
        time.sleep(0.5)
    raise AssertionError(f"timed out waiting for {msg}")


def send(user, item, event_id=None, kind="view"):
    r = c.post("/events", json={"event_id": event_id or uuid.uuid4().hex, "user_id": user, "item_id": item, "kind": kind})
    assert r.status_code == 202, r.text


def processed():
    return c.get("/stats").json().get("processed", 0)


@pytest.fixture(scope="module", autouse=True)
def ready():
    wait_until(lambda: c.get("/readyz").status_code == 200, 120, "api ready")


def test_recommendations_follow_what_similar_users_viewed():
    tag = uuid.uuid4().hex[:6]
    a, b = f"x-{tag}", f"y-{tag}"
    start = processed()
    for u in range(6):
        for item in (f"{tag}-shoes", f"{tag}-socks", f"{tag}-laces"):
            send(f"seed{u}-{tag}", item)
    send(a, f"{tag}-shoes")
    send(b, f"{tag}-unrelated")
    wait_until(lambda: processed() >= start + 20, 60, "worker to apply 20 events")
    items = c.get(f"/recommendations/{a}", params={"k": 5}).json()["items"]
    names = [i["item"] for i in items]
    assert f"{tag}-socks" in names and f"{tag}-laces" in names
    top = next(i for i in items if i["item"] == f"{tag}-socks")
    assert top["reason"] == f"because you viewed {tag}-shoes"


def test_duplicate_event_is_applied_once():
    before = c.get("/stats").json()
    eid = uuid.uuid4().hex
    send(f"dup-{eid}", f"dup-item-{eid}", event_id=eid)
    send(f"dup-{eid}", f"dup-item-{eid}", event_id=eid)
    wait_until(lambda: c.get("/stats").json().get("duplicates", 0) >= before.get("duplicates", 0) + 1, 60, "duplicate")
    assert c.get("/stats").json()["processed"] == before.get("processed", 0) + 1


def test_restricted_items_never_appear():
    tag = uuid.uuid4().hex[:6]
    start = processed()
    for u in range(4):
        send(f"s{u}-{tag}", f"{tag}-a")
        send(f"s{u}-{tag}", f"{tag}-secret")
    send(f"me-{tag}", f"{tag}-a")
    wait_until(lambda: processed() >= start + 9, 60, "events applied")
    assert c.post(f"/admin/restricted/{tag}-secret").status_code == 204
    names = [i["item"] for i in c.get(f"/recommendations/me-{tag}").json()["items"]]
    assert f"{tag}-secret" not in names


def test_new_user_gets_popular_items_with_a_reason():
    items = c.get(f"/recommendations/brand-new-{uuid.uuid4().hex}").json()["items"]
    assert items and all(i["reason"] == "popular right now" for i in items)


def test_bad_input_is_rejected():
    assert c.post("/events", json={"event_id": "x", "user_id": "", "item_id": "i"}).status_code == 422
    assert c.get("/recommendations/u", params={"k": 500}).status_code == 422


def test_metrics_endpoint_exposes_counters():
    body = c.get("/metrics").text
    assert "events_accepted_total" in body and "recommendation_seconds" in body


@pytest.mark.skipif(not COMPOSE, reason="needs the emulator and Redis ports")
def test_malformed_message_is_dead_lettered_not_retried_forever():
    from google.cloud import pubsub_v1
    before = c.get("/stats").json().get("dead_lettered", 0)
    pub = pubsub_v1.PublisherClient()
    pub.publish(pub.topic_path("lab-project", "events"), b"not json at all").result(timeout=10)
    wait_until(lambda: c.get("/stats").json().get("dead_lettered", 0) == before + 1, 60, "dead letter")


@pytest.mark.skipif(not COMPOSE, reason="needs the Redis port")
def test_raw_user_ids_never_reach_redis():
    import redis
    r = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    marker = f"person-{uuid.uuid4().hex}"
    send(marker, "privacy-item")
    wait_until(lambda: any(k.startswith("hist:") for k in r.keys("hist:*")), 30, "history key")
    assert not any(marker in k for k in r.keys("*"))


@pytest.mark.skipif(not COMPOSE, reason="needs docker compose")
def test_readiness_fails_when_redis_is_down_and_recovers():
    subprocess.run(["docker", "compose", "stop", "redis"], check=True, capture_output=True)
    try:
        wait_until(lambda: c.get("/readyz").status_code == 503, 30, "503 while redis is down")
        assert c.get("/healthz").status_code == 200  # liveness must not depend on redis
    finally:
        subprocess.run(["docker", "compose", "start", "redis"], check=True, capture_output=True)
    wait_until(lambda: c.get("/readyz").status_code == 200, 60, "recovery")
