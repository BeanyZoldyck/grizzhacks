"""WebSocket client for services backed by MongoDB.

MongoDB speaks its wire protocol over TCP, not WebSocket. Use this client against
a gateway (your API, proxy, or hackathon server) that holds a MongoClient and
exposes operations over ``ws://`` or ``wss://``.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import websockets
from dotenv import load_dotenv
from websockets.protocol import OPEN

_ENV_DIR = Path(__file__).resolve().parent


def load_env(path: Path | None = None) -> None:
    """Load ``.env`` from the ``mongo/`` directory (or ``path``) into ``os.environ``."""
    load_dotenv(path or _ENV_DIR / ".env")


class MongoWebSocketClient:
    """Async WebSocket client; pair with a running MongoDB via a WS gateway."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self._ws: websockets.ClientConnection | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.state is OPEN

    async def connect(self, **kwargs: Any) -> None:
        """Open the WebSocket. Extra kwargs are passed to ``websockets.connect``."""
        self._ws = await websockets.connect(self.uri, **kwargs)

    async def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            await ws.close()

    async def send_json(self, payload: dict[str, Any]) -> None:
        if not self._ws or self._ws.state is not OPEN:
            raise RuntimeError("WebSocket is not connected")
        await self._ws.send(json.dumps(payload))

    async def send_text(self, text: str) -> None:
        if not self._ws or self._ws.state is not OPEN:
            raise RuntimeError("WebSocket is not connected")
        await self._ws.send(text)

    async def recv(self) -> str:
        if not self._ws or self._ws.state is not OPEN:
            raise RuntimeError("WebSocket is not connected")
        msg = await self._ws.recv()
        if isinstance(msg, bytes):
            return msg.decode()
        return msg

    async def recv_json(self) -> Any:
        return json.loads(await self.recv())

    async def run_loop(
        self,
        on_message: Callable[[Any], Awaitable[None] | None] | None = None,
    ) -> None:
        """Receive messages until the connection closes or is cancelled."""
        if not self._ws:
            raise RuntimeError("WebSocket is not connected")
        async for raw in self._ws:
            if isinstance(raw, bytes):
                text = raw.decode()
            else:
                text = raw
            try:
                data: Any = json.loads(text)
            except json.JSONDecodeError:
                data = text
            if on_message is not None:
                maybe = on_message(data)
                if asyncio.iscoroutine(maybe):
                    await maybe


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


async def connect_and_listen(
    ws_uri: str,
    *,
    ping_mongo_first: str | None = None,
    on_message: Callable[[Any], Awaitable[None] | None] | None = None,
) -> None:
    """Optionally ping MongoDB, then connect WebSocket and run receive loop."""
    if ping_mongo_first is not None:
        # Run blocking ping in a thread so we do not block the event loop.
        await asyncio.to_thread(ping_mongodb, ping_mongo_first)

    client = MongoWebSocketClient(ws_uri)
    try:
        await client.connect()
        await client.run_loop(on_message=on_message)
    finally:
        await client.close()


def default_ws_uri() -> str:
    return os.environ.get("MONGODB_WS_URI") or "ws://127.0.0.1:8765"


def default_mongo_uri() -> str | None:
    """Atlas / cloud URI from ``MONGODB_URI`` (after :func:`load_env`)."""
    v = os.environ.get("MONGODB_URI")
    return v.strip() if v and v.strip() else None


def default_database() -> str | None:
    v = os.environ.get("MONGODB_DATABASE")
    return v.strip() if v and v.strip() else None


__all__ = [
    "MongoWebSocketClient",
    "connect_and_listen",
    "default_database",
    "default_mongo_uri",
    "default_ws_uri",
    "load_env",
    "ping_mongodb",
]
