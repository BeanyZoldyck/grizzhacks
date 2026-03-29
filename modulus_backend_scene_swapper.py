"""Hot-swap XML scene programs by polling MongoDB for updates.

Behavior:
1. Load environment via dotenv and read MONGODB_URI from os.environ.
2. Patch sockets for SOCKS5 proxy (PySocks), then initialize pymongo.
3. On startup, clear XML files in scenes/ and play default waiting scenes.
4. Poll embetter.lesson_plans every 10 seconds for newest document.
5. If newest document changed, replace scenes/ XML files and display them by
   StepTimeMain modulus buckets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import socks
from dotenv import load_dotenv

from lightguide_client import LightGuideClient


@dataclass
class SceneSet:
    programs: list[str]
    version: int
    source: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_env() -> None:
    repo_root = _repo_root()
    load_dotenv(override=True)
    load_dotenv(repo_root / "mongo" / ".env", override=True)


def _patch_socks_socket() -> None:
    proxy_host = os.environ.get("SOCKS_PROXY_HOST", "localhost")
    proxy_port = int(os.environ.get("SOCKS_PROXY_PORT", "1080"))

    socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
    socket.SOCK_CLOEXEC = 0
    socket.socket = socks.socksocket
    socks.wrapmodule(socket)


def _parse_step_time_main(payload: object) -> float:
    raw: object
    if isinstance(payload, dict):
        raw = payload.get("ResponseItem", payload)
    else:
        raw = payload

    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        return float(raw.strip())

    raise ValueError(f"Unsupported StepTimeMain payload: {payload!r}")


def _bucket_index(step_time_main: float, cycle_seconds: float, scene_count: int) -> int:
    phase = step_time_main % cycle_seconds
    bucket_size = cycle_seconds / scene_count
    idx = int(phase / bucket_size)
    return min(max(idx, 0), scene_count - 1)


def _clear_scene_xmls(scenes_dir: Path) -> None:
    if not scenes_dir.exists():
        return
    for path in scenes_dir.glob("*.xml"):
        path.unlink(missing_ok=True)


def _extract_xml_bundle_from_payload(payload: object) -> dict[str, str]:
    if isinstance(payload, str):
        payload = json.loads(payload)

    files: dict[str, str] = {}

    if isinstance(payload, dict):
        scenes_map = payload.get("scenes")
        if isinstance(scenes_map, dict):
            for name, content in scenes_map.items():
                if isinstance(name, str) and isinstance(content, str):
                    files[name] = content

        file_list = payload.get("files")
        if isinstance(file_list, list):
            for item in file_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("filename")
                content = item.get("content")
                if isinstance(name, str) and isinstance(content, str):
                    files[name] = content

        if not files:
            name = payload.get("name") or payload.get("filename")
            content = payload.get("content")
            if isinstance(name, str) and isinstance(content, str):
                files[name] = content

    if not files:
        raise ValueError("No XML files found in backend payload")

    cleaned: dict[str, str] = {}
    for name, content in files.items():
        file_name = Path(name).name
        if not file_name.lower().endswith(".xml"):
            continue
        cleaned[file_name] = content

    if not cleaned:
        raise ValueError("Payload had no .xml files")

    return cleaned


def _extract_xml_bundle_from_document(document: dict[str, Any]) -> dict[str, str]:
    candidates = [
        document.get("payload"),
        document.get("message"),
        document.get("text"),
        document.get("json"),
        document,
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return _extract_xml_bundle_from_payload(candidate)
        except Exception:
            continue

    raise ValueError("No XML bundle found in MongoDB document")


def _write_scene_bundle(scenes_dir: Path, files: dict[str, str]) -> list[str]:
    _clear_scene_xmls(scenes_dir)

    written: list[str] = []
    for file_name in sorted(files.keys()):
        if scenes_dir.exists():
            target = scenes_dir / file_name
            target.write_text(files[file_name], encoding="utf-8")
        written.append(f"scenes/{file_name}")
    return written


def _latest_lesson_plan_doc(mongo_uri: str, db_name: str, collection_name: str) -> dict[str, Any] | None:
    from pymongo import MongoClient

    client = MongoClient(mongo_uri)
    try:
        collection = client[db_name][collection_name]
        return collection.find_one(sort=[("_id", -1)])
    finally:
        client.close()


async def _mongo_poller(
    *,
    mongo_uri: str,
    db_name: str,
    collection_name: str,
    scenes_dir: Path,
    updates: asyncio.Queue[SceneSet],
    poll_seconds: float,
) -> None:
    version = 0
    last_seen_id: object | None = None

    while True:
        try:
            doc = await asyncio.to_thread(
                _latest_lesson_plan_doc,
                mongo_uri,
                db_name,
                collection_name,
            )
            if doc is None:
                await asyncio.sleep(poll_seconds)
                continue

            latest_id = doc.get("_id")
            if latest_id != last_seen_id:
                files = _extract_xml_bundle_from_document(doc)
                programs = _write_scene_bundle(scenes_dir, files)
                version += 1
                last_seen_id = latest_id
                await updates.put(
                    SceneSet(
                        programs=programs,
                        version=version,
                        source="backend",
                    )
                )
        except Exception:
            pass

        await asyncio.sleep(poll_seconds)


async def _player_loop(
    *,
    base_url: str,
    cycle_seconds: float,
    poll_seconds: float,
    updates: asyncio.Queue[SceneSet],
    default_programs: list[str],
) -> None:
    client = LightGuideClient(base_url=base_url)

    await asyncio.to_thread(client.abort)
    await asyncio.to_thread(client.run_mode)

    active = SceneSet(programs=default_programs, version=0, source="default")
    last_program: str | None = None
    seen_version = -1

    while True:
        try:
            while True:
                active = updates.get_nowait()
        except asyncio.QueueEmpty:
            pass

        if not active.programs:
            await asyncio.sleep(poll_seconds)
            continue

        step_payload = await asyncio.to_thread(client.get_variable, "StepTimeMain")
        step_time_main = _parse_step_time_main(step_payload)
        idx = _bucket_index(step_time_main, cycle_seconds, len(active.programs))
        target_program = active.programs[idx]

        if target_program != last_program or active.version != seen_version:
            await asyncio.to_thread(client.run_program, target_program, False)
            await asyncio.to_thread(
                client.message,
                f"{active.source} scene {idx + 1}/{len(active.programs)}: {target_program}",
            )
            last_program = target_program
            seen_version = active.version

        await asyncio.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Swap XML programs from MongoDB poll using StepTimeMain modulus",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LIGHTGUIDE_BASE_URL", "http://127.0.0.1:54274"),
        help="LightGuide API base URL",
    )
    parser.add_argument(
        "--cycle-seconds",
        type=float,
        default=10.0,
        help="Total seconds for one full scene cycle",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=0.2,
        help="Polling interval for StepTimeMain",
    )
    parser.add_argument(
        "--mongo-poll-seconds",
        type=float,
        default=10.0,
        help="Polling interval for MongoDB lesson updates",
    )
    parser.add_argument(
        "--mongo-db",
        default="embetter",
        help="MongoDB database name",
    )
    parser.add_argument(
        "--mongo-collection",
        default="lesson_plans",
        help="MongoDB collection name",
    )
    parser.add_argument(
        "--scenes-dir",
        default="scenes",
        help="Optional local folder for streamed scene XML files (write/clean skipped if missing)",
    )
    parser.add_argument(
        "--default-program",
        action="append",
        dest="default_programs",
        help=(
            "Program path for waiting animation. Repeat for multiple files. "
            "Defaults to default/Waiting1.xml and default/Waiting2.xml"
        ),
    )
    return parser


async def _main_async(args: argparse.Namespace) -> None:
    _load_env()
    _patch_socks_socket()

    mongo_uri = os.environ.get("MONGODB_URI", "").strip()
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is required")

    scenes_dir = Path(args.scenes_dir)

    _clear_scene_xmls(scenes_dir)

    default_programs = args.default_programs or ["default/Waiting1.xml", "default/Waiting2.xml"]

    updates: asyncio.Queue[SceneSet] = asyncio.Queue()

    poller_task = asyncio.create_task(
        _mongo_poller(
            mongo_uri=mongo_uri,
            db_name=args.mongo_db,
            collection_name=args.mongo_collection,
            scenes_dir=scenes_dir,
            updates=updates,
            poll_seconds=args.mongo_poll_seconds,
        )
    )

    player_task = asyncio.create_task(
        _player_loop(
            base_url=args.base_url,
            cycle_seconds=args.cycle_seconds,
            poll_seconds=args.poll_seconds,
            updates=updates,
            default_programs=default_programs,
        )
    )

    await asyncio.gather(poller_task, player_task)


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
