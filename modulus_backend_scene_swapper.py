"""Hot-swap XML scene programs from backend text stream.

Behavior:
1. Load environment via dotenv and read MONGODB_URI from os.environ.
2. Connect to backend WebSocket (URI from MONGODB_URI).
3. On startup, clear XML files in scenes/ and play default waiting scenes.
4. When an XML batch arrives over WebSocket text stream, replace scenes/ files
   and display them by StepTimeMain modulus buckets.
5. On each subsequent batch, replace scenes/ again and continue.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets
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
    load_dotenv()
    load_dotenv(repo_root / "mongo" / ".env")


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
    scenes_dir.mkdir(parents=True, exist_ok=True)
    for path in scenes_dir.glob("*.xml"):
        path.unlink(missing_ok=True)


def _extract_xml_bundle(message_text: str) -> dict[str, str]:
    payload = json.loads(message_text)

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
        raise ValueError("Backend payload had no .xml files")

    return cleaned


def _write_scene_bundle(scenes_dir: Path, files: dict[str, str]) -> list[str]:
    _clear_scene_xmls(scenes_dir)

    written: list[str] = []
    for file_name in sorted(files.keys()):
        target = scenes_dir / file_name
        target.write_text(files[file_name], encoding="utf-8")
        written.append(f"scenes/{file_name}")
    return written


async def _backend_listener(
    *,
    ws_uri: str,
    scenes_dir: Path,
    updates: asyncio.Queue[SceneSet],
    reconnect_seconds: float,
) -> None:
    version = 0
    while True:
        try:
            async with websockets.connect(ws_uri, max_size=None) as ws:
                async for message in ws:
                    if isinstance(message, bytes):
                        text = message.decode()
                    else:
                        text = message

                    files = _extract_xml_bundle(text)
                    programs = _write_scene_bundle(scenes_dir, files)
                    version += 1
                    await updates.put(
                        SceneSet(
                            programs=programs,
                            version=version,
                            source="backend",
                        )
                    )
        except Exception:
            await asyncio.sleep(reconnect_seconds)


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
        description="Swap XML programs from backend stream using StepTimeMain modulus",
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
        "--reconnect-seconds",
        type=float,
        default=1.0,
        help="WebSocket reconnect delay",
    )
    parser.add_argument(
        "--scenes-dir",
        default=str(_repo_root() / "scenes"),
        help="Folder where streamed scene XML files are written",
    )
    parser.add_argument(
        "--default-dir",
        default=str(_repo_root() / "default"),
        help="Folder containing waiting scene XML files",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> None:
    _load_env()

    ws_uri = os.environ.get("MONGODB_URI", "ws://141.210.86.11:8765").strip()
    if not ws_uri:
        raise RuntimeError("MONGODB_URI is required and must be a ws:// or wss:// URL")
    if not (ws_uri.startswith("ws://") or ws_uri.startswith("wss://")):
        raise RuntimeError("MONGODB_URI must be a ws:// or wss:// URL for backend stream")

    scenes_dir = Path(args.scenes_dir).resolve()
    default_dir = Path(args.default_dir).resolve()

    _clear_scene_xmls(scenes_dir)

    default_programs = sorted([f"default/{p.name}" for p in default_dir.glob("*.xml")])
    if not default_programs:
        raise RuntimeError(f"No default XML files found in {default_dir}")

    updates: asyncio.Queue[SceneSet] = asyncio.Queue()

    listener_task = asyncio.create_task(
        _backend_listener(
            ws_uri=ws_uri,
            scenes_dir=scenes_dir,
            updates=updates,
            reconnect_seconds=args.reconnect_seconds,
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

    await asyncio.gather(listener_task, player_task)


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
