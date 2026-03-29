"""Server-side LightGuide runner for XML lesson payloads.

This service connects to the Mongo-backed WebSocket gateway, receives XML lesson
payloads from the client side, writes them to the LightGuide program folders, and
controls execution on the LightGuide machine through LightGuidePy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from websocket_client import (
    MongoWebSocketClient,
    default_mongo_uri,
    default_ws_uri,
    load_env,
    ping_mongodb,
)


def _sdk_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "LightGuidePy-main" / "LightGuidePy"


import sys

sys.path.insert(0, str(_sdk_path()))
from lightguide_client import LightGuideClient  # noqa: E402


@dataclass
class LessonState:
    program_path: str | None = None
    current_step: int = 0
    total_steps: int = 0
    complete: bool = False


class LightGuideLessonRunner:
    def __init__(
        self,
        *,
        ws_uri: str,
        base_url: str,
        program_root: Path,
    ) -> None:
        self.ws_uri = ws_uri
        self.program_root = program_root
        self.viz_dir = program_root / "viz"
        self.tools_dir = program_root / "tools"
        self.client = LightGuideClient(base_url=base_url)
        self.ws_client = MongoWebSocketClient(ws_uri)
        self.state = LessonState()

    async def run(self) -> None:
        self.viz_dir.mkdir(parents=True, exist_ok=True)
        self.tools_dir.mkdir(parents=True, exist_ok=True)

        await self.ws_client.connect()
        await self._send_status("ready", "LightGuide lesson runner connected")
        try:
            await self.ws_client.run_loop(on_message=self._on_message)
        finally:
            await self.ws_client.close()

    async def _on_message(self, data: Any) -> None:
        if not isinstance(data, dict):
            await self._send_error("invalid_payload", "Expected JSON object")
            return

        msg_type = str(data.get("type", "")).lower().strip()
        if msg_type in {"lesson_xml", "xml_bundle", "lesson_upload"}:
            await self._handle_xml_bundle(data)
            return

        if msg_type in {"lesson_control", "execution"}:
            await self._handle_control(data)
            return

        await self._send_error(
            "unknown_type",
            f"Unsupported message type: {data.get('type')!r}",
        )

    async def _handle_xml_bundle(self, payload: dict[str, Any]) -> None:
        written = []

        for category in ("viz", "tools"):
            files = self._extract_category_files(payload, category)
            target_dir = self.viz_dir if category == "viz" else self.tools_dir
            for filename, content in files:
                dest = self._safe_child(target_dir, filename)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                written.append(str(dest.relative_to(self.program_root)))

        program_path = self._pick_program(payload)
        step_count = int(payload.get("step_count") or payload.get("steps") or 0)
        self.state = LessonState(
            program_path=program_path,
            current_step=0,
            total_steps=max(step_count, 0),
            complete=False,
        )

        await asyncio.to_thread(self._refresh_and_start_program, program_path)
        await self._sync_state_variables()

        await self._send_status(
            "lesson_loaded",
            "XML files received and LightGuide program started",
            {
                "program": program_path,
                "written_files": written,
                "step_count": self.state.total_steps,
            },
        )

    async def _handle_control(self, payload: dict[str, Any]) -> None:
        action = str(payload.get("action", "")).lower().strip()
        if action not in {"next", "back", "restart", "abort"}:
            await self._send_error("invalid_action", f"Unsupported action: {action!r}")
            return

        await asyncio.to_thread(self._apply_action, action)
        await self._sync_state_variables()

        info = {
            "action": action,
            "current_step": self.state.current_step,
            "total_steps": self.state.total_steps,
            "complete": self.state.complete,
        }
        await self._send_status("lesson_progress", "Execution action applied", info)

    def _extract_category_files(
        self,
        payload: dict[str, Any],
        category: str,
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []

        raw_map = payload.get(category)
        if isinstance(raw_map, dict):
            for name, content in raw_map.items():
                if isinstance(name, str) and isinstance(content, str):
                    out.append((name, content))

        raw_files = payload.get("files")
        if isinstance(raw_files, list):
            for item in raw_files:
                if not isinstance(item, dict):
                    continue
                file_category = str(item.get("category") or item.get("folder") or "").lower()
                if file_category != category:
                    continue
                name = item.get("name") or item.get("filename")
                content = item.get("content")
                if isinstance(name, str) and isinstance(content, str):
                    out.append((name, content))

        return out

    def _pick_program(self, payload: dict[str, Any]) -> str:
        program = payload.get("program") or payload.get("program_path")
        if isinstance(program, str) and program.strip():
            return program.strip()

        default_program = os.environ.get("LIGHTGUIDE_DEFAULT_PROGRAM")
        if default_program and default_program.strip():
            return default_program.strip()

        return "viz/main.xml"

    def _refresh_and_start_program(self, program_path: str) -> None:
        try:
            self.client.abort()
        except Exception:
            pass

        try:
            self.client.run_mode()
        except Exception:
            pass

        self.client.run_program(program_path, wait=False)
        self.client.message(f"Lesson started: {program_path}")

    def _apply_action(self, action: str) -> None:
        if action == "next":
            self.client.next()
            self.state.current_step += 1

            if self.state.total_steps > 0 and self.state.current_step >= self.state.total_steps:
                self.state.complete = True
                self.client.message("Lesson Complete!")

        elif action == "back":
            self.client.back()
            self.state.current_step = max(self.state.current_step - 1, 0)
            self.state.complete = False

        elif action == "restart":
            self.client.restart()
            self.state.current_step = 0
            self.state.complete = False

        elif action == "abort":
            self.client.abort()
            self.state.complete = False

    async def _sync_state_variables(self) -> None:
        updates = [
            {"Name": "LessonCurrentStep", "Type": "Integer", "Value": str(self.state.current_step)},
            {"Name": "LessonComplete", "Type": "Boolean", "Value": str(self.state.complete)},
        ]

        if self.state.program_path:
            updates.append(
                {
                    "Name": "LessonProgram",
                    "Type": "String",
                    "Value": self.state.program_path,
                }
            )

        try:
            await asyncio.to_thread(self.client.set_variables, updates)
        except Exception as exc:
            await self._send_error("set_variables_failed", str(exc))

    async def _send_status(
        self,
        status: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "type": "lightguide_status",
            "status": status,
            "message": message,
        }
        if data:
            payload["data"] = data
        await self.ws_client.send_json(payload)

    async def _send_error(self, code: str, message: str) -> None:
        try:
            await asyncio.to_thread(self.client.error_message, message)
        except Exception:
            pass

        await self.ws_client.send_json(
            {
                "type": "lightguide_error",
                "error": code,
                "message": message,
            }
        )

    def _safe_child(self, root: Path, relative_name: str) -> Path:
        cleaned = relative_name.replace("\\", "/").lstrip("/")
        candidate = (root / cleaned).resolve()
        root_resolved = root.resolve()
        if candidate == root_resolved:
            raise ValueError("File path must include a file name")
        if root_resolved not in candidate.parents:
            raise ValueError(f"Illegal file path outside target folder: {relative_name!r}")
        return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Receive XML lesson payloads from a WebSocket bridge and run them on "
            "LightGuide through LightGuidePy."
        )
    )
    parser.add_argument(
        "--ws-uri",
        default=default_ws_uri(),
        help="WebSocket URL (default: MONGODB_WS_URI or ws://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--mongo-uri",
        default=default_mongo_uri(),
        help="MongoDB connection string used only for optional --ping-mongo",
    )
    parser.add_argument(
        "--ping-mongo",
        action="store_true",
        help="Ping MongoDB before starting the WebSocket loop",
    )
    parser.add_argument(
        "--lightguide-url",
        default=os.environ.get("LIGHTGUIDE_BASE_URL", "http://127.0.0.1:54274"),
        help="LightGuide base URL",
    )
    parser.add_argument(
        "--program-root",
        default=os.environ.get("LIGHTGUIDE_PROGRAM_ROOT", str(Path(__file__).resolve().parent / "programs")),
        help="Local root folder where received XMLs are written (creates viz/ and tools/)",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> None:
    if args.ping_mongo:
        if args.mongo_uri:
            await asyncio.to_thread(ping_mongodb, args.mongo_uri)
        else:
            await asyncio.to_thread(ping_mongodb)

    runner = LightGuideLessonRunner(
        ws_uri=args.ws_uri,
        base_url=args.lightguide_url,
        program_root=Path(args.program_root),
    )
    await runner.run()


def main() -> None:
    load_env()
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
