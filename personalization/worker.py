"""Consumes events from Pub/Sub and updates Redis. Bad messages go to a dead-letter topic, not an infinite retry."""
import json
import signal
import sys

from . import bus, store
from .events import Event
from .logs import log
from .privacy import user_key

from google.cloud import pubsub_v1


def main() -> None:
    bus.ensure_topology()
    r = store.client()
    sub = pubsub_v1.SubscriberClient()
    pub = bus.publisher()
    path = sub.subscription_path(bus.PROJECT, bus.SUB)
    dead_topic = pub.topic_path(bus.PROJECT, bus.DEAD_TOPIC)

    def handle(msg: pubsub_v1.subscriber.message.Message) -> None:
        try:
            ev = Event.model_validate_json(msg.data)
        except Exception as e:
            pub.publish(dead_topic, msg.data, reason=e.__class__.__name__).result(timeout=10)
            r.hincrby("stats", "dead_lettered", 1)
            log("warn", "event dead-lettered", reason=e.__class__.__name__)
            msg.ack()
            return
        try:
            applied = store.apply_event(r, user_key(ev.user_id), ev.item_id, ev.ts.timestamp(), ev.event_id)
            log("info", "event applied" if applied else "duplicate ignored", event_id=ev.event_id)
            msg.ack()
        except Exception as e:  # Redis down: let Pub/Sub redeliver
            log("error", "apply failed, will retry", error=e.__class__.__name__)
            msg.nack()

    future = sub.subscribe(path, callback=handle)
    log("info", "worker started", subscription=path)

    def stop(*_):
        future.cancel()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()


if __name__ == "__main__":
    main()
