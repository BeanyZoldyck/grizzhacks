"""CLI: optional MongoDB ping, then WebSocket client to a Mongo-backed gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from websocket_client import (
    connect_and_listen,
    default_mongo_uri,
    default_ws_uri,
    load_env,
    ping_mongodb,
)

load_env()


async def _main_async(args: argparse.Namespace) -> None:
    if args.ping_mongo:
        mongo_uri = args.mongo_uri
        if mongo_uri is None:
            ping_mongodb()
        else:
            ping_mongodb(mongo_uri)

    async def on_message(data: object) -> None:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2))
        else:
            print(data)

    await connect_and_listen(
        args.ws_uri,
        ping_mongo_first=None,
        on_message=on_message,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WebSocket client for a service that uses MongoDB "
        "(Mongo itself is TCP; point --ws-uri at your gateway).",
    )
    parser.add_argument(
        "--ws-uri",
        default=default_ws_uri(),
        help="WebSocket URL (default: env MONGODB_WS_URI or ws://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--mongo-uri",
        default=default_mongo_uri(),
        help="MongoDB connection string (default: MONGODB_URI from .env, else localhost for ping)",
    )
    parser.add_argument(
        "--ping-mongo",
        action="store_true",
        help="Run admin ping against MongoDB before opening the WebSocket",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
