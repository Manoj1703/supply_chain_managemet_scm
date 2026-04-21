from __future__ import annotations

import json
import os
import threading
from typing import Any

from database.db import create_history_entry, upsert_device

try:
    from kafka import KafkaConsumer, KafkaProducer
except ImportError:  # pragma: no cover - optional dependency
    KafkaConsumer = None
    KafkaProducer = None


KAFKA_BOOTSTRAP_SERVERS = [
    server.strip()
    for server in os.getenv("KAFKA_BOOTSTRAP_SERVERS", "").split(",")
    if server.strip()
]
KAFKA_DEVICE_TOPIC = os.getenv("KAFKA_DEVICE_TOPIC", "device-events")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "scm-device-consumer")

_consumer_started = False


def kafka_enabled() -> bool:
    return bool(KAFKA_BOOTSTRAP_SERVERS) and KafkaProducer is not None and KafkaConsumer is not None


def publish_device_event(event: dict[str, Any]) -> dict[str, Any]:
    if not kafka_enabled():
        device = upsert_device(
            device_id=event["device_id"],
            name=event.get("name"),
            status=event.get("status", "online"),
            location=event.get("location"),
            payload=event,
            source="mongo-fallback",
        )
        return {
            "status": "stored",
            "transport": "mongo-fallback",
            "device": device,
        }

    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )
        producer.send(KAFKA_DEVICE_TOPIC, event)
        producer.flush()
        producer.close()
        return {
            "status": "queued",
            "transport": "kafka",
            "topic": KAFKA_DEVICE_TOPIC,
            "device_id": event["device_id"],
        }
    except Exception:
        device = upsert_device(
            device_id=event["device_id"],
            name=event.get("name"),
            status=event.get("status", "online"),
            location=event.get("location"),
            payload=event,
            source="mongo-fallback",
        )
        return {
            "status": "stored",
            "transport": "mongo-fallback",
            "device": device,
        }


def _consume_device_events() -> None:
    try:
        consumer = KafkaConsumer(
            KAFKA_DEVICE_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id=KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

        for message in consumer:
            event = message.value
            if not isinstance(event, dict) or "device_id" not in event:
                continue
            upsert_device(
                device_id=event["device_id"],
                name=event.get("name"),
                status=event.get("status", "online"),
                location=event.get("location"),
                payload=event,
                source="kafka",
            )
    except Exception:
        return


def start_device_consumer() -> bool:
    global _consumer_started
    if _consumer_started or not kafka_enabled():
        return False

    thread = threading.Thread(target=_consume_device_events, daemon=True)
    thread.start()
    _consumer_started = True
    return True
