"""Build lesson documents and persist to MongoDB (direct PyMongo)."""

from __future__ import annotations

import socks
import socket

socks.set_default_proxy(socks.SOCKS5, "localhost", 1080)
socket.socket = socks.socksocket
if hasattr(socket, "SOCK_CLOEXEC"):
    socket.SOCK_CLOEXEC = 0

import asyncio
import functools
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from websocket_client import default_database, default_mongo_uri, load_env

SCHEMA_VERSION = 2


def lesson_cloud_enabled() -> bool:
    v = os.environ.get("LESSON_CLOUD", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def build_lesson_document(
    lesson_name: str,
    steps: list[dict[str, Any]],
    *,
    description: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lesson_name": lesson_name,
        "steps": steps,
    }
    if description is not None:
        doc["description"] = description
    if source is not None:
        doc["source"] = source
    if metadata is not None:
        doc["metadata"] = metadata
    return doc


def _persist_sync(
    lesson_name: str,
    steps: list[dict[str, Any]],
    *,
    description: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from pymongo import MongoClient
    from pymongo.errors import (
        ConnectionFailure,
        PyMongoError,
        ServerSelectionTimeoutError,
    )

    load_env()
    uri = default_mongo_uri() or os.environ.get("MONGODB_URI")
    if not uri or not str(uri).strip():
        raise RuntimeError("MONGODB_URI is required to persist lessons")
    uri = str(uri).strip()
    db_name = (
        default_database() or os.environ.get("MONGODB_DATABASE") or ""
    ).strip() or "embettered"
    coll_name = (
        os.environ.get("LESSON_PLANS_COLLECTION", "lesson_plans").strip()
        or "lesson_plans"
    )

    print(f"[MongoDB Debug] Attempting to connect...")
    print(f"[MongoDB Debug] MONGODB_URI: {uri}")
    print(f"[MongoDB Debug] Database: {db_name}")
    print(f"[MongoDB Debug] Collection: {coll_name}")
    print(f"[MongoDB Debug] Lesson name: {lesson_name}")

    doc = build_lesson_document(
        lesson_name,
        steps,
        description=description,
        source=source,
        metadata=metadata,
    )
    doc["createdAt"] = datetime.now(timezone.utc)
    doc["ingestId"] = str(uuid.uuid4())

    print(f"[MongoDB Debug] Creating MongoDB client...")
    client = None
    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
        )
        print(f"[MongoDB Debug] Client created, testing connection...")
        client.admin.command("ping")
        print(f"[MongoDB Debug] Connection successful!")
        print(f"[MongoDB Debug] Inserting document...")
        result = client[db_name][coll_name].insert_one(doc)
        print(f"[MongoDB Debug] Insert successful! ID: {result.inserted_id}")
    except ServerSelectionTimeoutError as e:
        print(f"[MongoDB Error] Server selection timeout: {e}")
        print(
            f"[MongoDB Error] This usually means MongoDB server is not reachable or the URI is incorrect"
        )
        raise RuntimeError(f"MongoDB connection timeout: {e}") from e
    except ConnectionFailure as e:
        print(f"[MongoDB Error] Connection failure: {e}")
        print(f"[MongoDB Error] Details: {type(e).__name__}")
        raise RuntimeError(f"MongoDB connection failed: {e}") from e
    except PyMongoError as e:
        print(f"[MongoDB Error] PyMongo error: {e}")
        print(f"[MongoDB Error] Details: {type(e).__name__}")
        raise RuntimeError(f"MongoDB operation failed: {e}") from e
    except Exception as e:
        print(f"[MongoDB Error] Unexpected error: {e}")
        print(f"[MongoDB Error] Type: {type(e).__name__}")
        raise RuntimeError(f"Unexpected MongoDB error: {e}") from e
    finally:
        if client:
            print(f"[MongoDB Debug] Closing connection...")
            client.close()
            print(f"[MongoDB Debug] Connection closed")

    return {
        "type": "ack",
        "schema_version": SCHEMA_VERSION,
        "inserted_id": str(result.inserted_id),
    }


async def persist_lesson_async(
    lesson_name: str,
    steps: list[dict[str, Any]],
    *,
    description: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    fn = functools.partial(
        _persist_sync,
        lesson_name,
        steps,
        description=description,
        source=source,
        metadata=metadata,
    )
    resp = await asyncio.to_thread(fn)
    if verbose and isinstance(resp, dict):
        print(f"MongoDB: {json.dumps(resp, indent=2)}")
    return resp


async def send_lesson_to_mongodb(
    lesson_name: str,
    steps: list[dict[str, Any]],
    *,
    description: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    enable_cloud: bool | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Persist lesson to MongoDB when ``enable_cloud`` / ``LESSON_CLOUD`` allows."""
    if enable_cloud is None:
        enable_cloud = lesson_cloud_enabled()
    if not enable_cloud:
        if verbose:
            print("Skipping MongoDB (LESSON_CLOUD disabled or --no-cloud).")
        return {"skipped": True}

    if verbose:
        print(f"Persisting lesson '{lesson_name}' to MongoDB...")
    resp = await persist_lesson_async(
        lesson_name,
        steps,
        description=description,
        source=source,
        metadata=metadata,
        verbose=verbose,
    )
    return {**resp, "cloud_ack": resp}
