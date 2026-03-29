"""Shared helpers: load ``mongo/.env`` and read MongoDB settings (``pymongo`` ping)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_DIR = Path(__file__).resolve().parent


def load_env(path: Path | None = None) -> None:
    """Load ``.env`` from the ``mongo/`` directory (or ``path``) into ``os.environ``."""
    load_dotenv(path or _ENV_DIR / ".env", override=True)


def ping_mongodb(
    uri: str | None = None,
    *,
    timeout_ms: int = 5000,
) -> None:
    """Raise if MongoDB is not reachable (``pymongo``)."""
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError

    mongo_uri = uri or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017"
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=timeout_ms)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError as e:
        raise RuntimeError(f"MongoDB not reachable at {mongo_uri!r}") from e
    finally:
        client.close()


def default_mongo_uri() -> str | None:
    """Atlas / cloud URI from ``MONGODB_URI`` (after :func:`load_env`)."""
    v = os.environ.get("MONGODB_URI")
    return v.strip() if v and v.strip() else None


def default_database() -> str | None:
    v = os.environ.get("MONGODB_DATABASE")
    return v.strip() if v and v.strip() else None


__all__ = [
    "default_database",
    "default_mongo_uri",
    "load_env",
    "ping_mongodb",
]
