"""HTTP API. Accepts events (publishes them to Pub/Sub) and serves recommendations from Redis."""
import os
import time

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import bus, scoring, store
from .events import Event
from .logs import log
from .privacy import user_key

app = FastAPI(title="personalization-lab")
r = store.client()
pub = None

EVENTS_IN = Counter("events_accepted_total", "Events accepted and published")
REC_LATENCY = Histogram("recommendation_seconds", "Recommendation latency")
REC_FALLBACK = Counter("recommendation_popularity_fallback_total", "Responses padded with popular items")


@app.on_event("startup")
def startup():
    global pub
    bus.ensure_topology()
    pub = bus.publisher()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        r.ping()
    except Exception:
        raise HTTPException(503, "redis unavailable")
    return {"status": "ready"}


@app.post("/events", status_code=202)
def post_event(ev: Event):
    topic = pub.topic_path(bus.PROJECT, bus.TOPIC)
    pub.publish(topic, ev.model_dump_json().encode()).result(timeout=10)
    EVENTS_IN.inc()
    log("info", "event accepted", event_id=ev.event_id, kind=ev.kind, user=user_key(ev.user_id), item=ev.item_id)
    return {"accepted": ev.event_id}


@app.get("/recommendations/{user_id}")
def recommendations(user_id: str, k: int = 10):
    if not 1 <= k <= 50:
        raise HTTPException(422, "k must be between 1 and 50")
    t0 = time.time()
    history, cooc, pop, restricted = store.load_for_user(r, user_key(user_id))
    recs = scoring.recommend(history, cooc, pop, restricted, k)
    REC_LATENCY.observe(time.time() - t0)
    if any(reason == "popular right now" for _, _, reason in recs):
        REC_FALLBACK.inc()
    log("info", "recommendations served", user=user_key(user_id), n=len(recs), history=len(history),
        ms=round((time.time() - t0) * 1000, 1))
    return {"items": [{"item": i, "score": s, "reason": why} for i, s, why in recs]}


@app.post("/admin/restricted/{item_id}", status_code=204)
def restrict(item_id: str):
    r.sadd("restricted", item_id)


@app.get("/stats")
def stats():
    return {k: int(v) for k, v in r.hgetall("stats").items()}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
