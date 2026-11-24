"""Google Cloud Pub/Sub. Uses the emulator when PUBSUB_EMULATOR_HOST is set."""
import os

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

PROJECT = os.environ.get("GCP_PROJECT", "lab-project")
TOPIC = "events"
DEAD_TOPIC = "events-dead"
SUB = "events-worker"


def ensure_topology() -> None:
    pub, sub = pubsub_v1.PublisherClient(), pubsub_v1.SubscriberClient()
    topic, dead = pub.topic_path(PROJECT, TOPIC), pub.topic_path(PROJECT, DEAD_TOPIC)
    for t in (topic, dead):
        try:
            pub.create_topic(request={"name": t})
        except AlreadyExists:
            pass
    try:
        sub.create_subscription(request={"name": sub.subscription_path(PROJECT, SUB), "topic": topic,
                                         "ack_deadline_seconds": 20})
    except AlreadyExists:
        pass


def publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()
