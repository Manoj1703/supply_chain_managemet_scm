from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "shipment_api")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_database():
    return get_client()[MONGODB_DB_NAME]


def get_users_collection() -> Collection[dict[str, Any]]:
    return get_database()["users"]


def get_login_attempts_collection() -> Collection[dict[str, Any]]:
    return get_database()["login_attempts"]


def get_devices_collection() -> Collection[dict[str, Any]]:
    return get_database()["devices"]


def get_shipments_collection() -> Collection[dict[str, Any]]:
    return get_database()["shipments"]


def get_history_collection() -> Collection[dict[str, Any]]:
    return get_database()["history"]


def init_db() -> bool:
    try:
        get_client().admin.command("ping")
        get_users_collection().create_index("email", unique=True)
        get_login_attempts_collection().create_index("email")
        get_login_attempts_collection().create_index("created_at")
        get_devices_collection().create_index("device_id", unique=True)
        get_devices_collection().create_index("updated_at")
        get_shipments_collection().create_index("shipment_id", unique=True)
        get_shipments_collection().create_index("created_at")
        get_history_collection().create_index("created_at")
        return True
    except ServerSelectionTimeoutError:
        return False


def is_db_connected() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except ServerSelectionTimeoutError:
        return False


def create_user(name: str, email: str, salt: str, password_hash: str) -> dict[str, Any]:
    document = {
        "name": name,
        "email": email,
        "salt": salt,
        "password_hash": password_hash,
    }
    result = get_users_collection().insert_one(document)
    return {
        "id": str(result.inserted_id),
        **document,
    }


def get_user_by_email(email: str) -> dict[str, Any] | None:
    row = get_users_collection().find_one(
        {"email": email},
        {"name": 1, "email": 1, "salt": 1, "password_hash": 1},
    )

    if row is None:
        return None

    return {
        "id": str(row["_id"]),
        "name": row["name"],
        "email": row["email"],
        "salt": row["salt"],
        "password_hash": row["password_hash"],
    }


def create_login_attempt(email: str, success: bool, user_id: str | None = None) -> None:
    get_login_attempts_collection().insert_one(
        {
            "email": email,
            "user_id": user_id,
            "success": success,
            "created_at": datetime.now(timezone.utc),
        }
    )


def _public_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    result = {"id": str(document["_id"])}
    for key, value in document.items():
        if key != "_id":
            result[key] = value
    return result


def list_devices(limit: int = 100) -> list[dict[str, Any]]:
    return [
        _public_document(document)
        for document in get_devices_collection().find().sort("updated_at", -1).limit(limit)
    ]


def upsert_device(
    device_id: str,
    name: str | None,
    status: str,
    location: str | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "device_id": device_id,
        "name": name or device_id,
        "status": status,
        "location": location,
        "payload": payload or {},
        "source": source,
        "updated_at": now,
    }
    get_devices_collection().update_one(
        {"device_id": device_id},
        {
            "$set": document,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    stored = get_devices_collection().find_one({"device_id": device_id})
    create_history_entry(
        kind="device",
        message=f"Device {device_id} updated from {source}",
        entity_id=device_id,
        payload=document,
    )
    return _public_document(stored) or {}


def create_shipment(
    sender: str,
    receiver: str,
    status: str,
    eta: str | None = None,
    details: str | None = None,
    shipment_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    shipment_id = shipment_id or f"SH-{uuid4().hex[:8].upper()}"
    document = {
        "shipment_id": shipment_id,
        "sender": sender,
        "receiver": receiver,
        "status": status,
        "eta": eta,
        "details": details,
        "created_at": now,
        "updated_at": now,
    }
    result = get_shipments_collection().insert_one(document)
    create_history_entry(
        kind="shipment",
        message=f"Shipment {shipment_id} created",
        entity_id=shipment_id,
        payload=document,
    )
    return {
        "id": str(result.inserted_id),
        **document,
    }


def list_shipments(limit: int = 100) -> list[dict[str, Any]]:
    return [
        _public_document(document)
        for document in get_shipments_collection().find().sort("created_at", -1).limit(limit)
    ]


def create_history_entry(
    kind: str,
    message: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = {
        "kind": kind,
        "message": message,
        "entity_id": entity_id,
        "payload": payload or {},
        "created_at": datetime.now(timezone.utc),
    }
    result = get_history_collection().insert_one(document)
    return {
        "id": str(result.inserted_id),
        **document,
    }


def list_history(limit: int = 100) -> list[dict[str, Any]]:
    return [
        _public_document(document)
        for document in get_history_collection().find().sort("created_at", -1).limit(limit)
    ]
