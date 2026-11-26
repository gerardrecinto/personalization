# personalization-lab

A backend recommendation service built the way a cloud-native team would: an API, an event-driven worker on Google Pub/Sub, Redis for features, tests against the real stack, and logs a Splunk search can read.

Site: https://gerardrecinto.github.io/personalization-lab/

## How it works

```
POST /events -> API -> Pub/Sub topic -> worker -> Redis (counts, co-occurrence, history)
GET /recommendations/{user} -> API reads Redis -> item-item cosine scores, popularity for new users
```

- Users are stored under a keyed hash, never as the raw id.
- Duplicate events are applied once. Malformed messages go to a dead-letter topic.
- Restricted items can be blocked and never appear in results.
- Each recommendation carries a reason ("because you viewed X").
- `/healthz` for liveness, `/readyz` for readiness (fails when Redis is down), `/metrics` for Prometheus, one JSON log line per action.

## What the tests prove

| Test | Result |
|---|---|
| Item-item beats popularity offline (recall@10, synthetic data with planted taste groups) | 0.284 vs 0.050 |
| Similar users' items are recommended, with the right reason | passes |
| Duplicate event applied once | passes |
| Restricted item never returned | passes |
| New user gets popular items | passes |
| Malformed Pub/Sub message is dead-lettered, not retried forever | passes (emulator) |
| Raw user ids never appear in Redis | passes |
| Readiness is 503 with Redis down, liveness stays 200, recovers | passes |
| Same end-to-end tests on Kubernetes (kind) | CI |
| JSON logs shipped to a real Splunk over HEC and found by search | CI |
| Z-test for an A/B comparison of click-through | passes |

## Run it

```bash
docker compose up -d --build
pip install -r requirements-dev.txt
STACK=compose PUBSUB_EMULATOR_HOST=localhost:8085 pytest
curl -s localhost:8000/recommendations/some-user
docker compose down -v
```

Needs Docker and Python 3.10+. The first start pulls the Pub/Sub emulator image (about 1 GB).

MIT licensed.
