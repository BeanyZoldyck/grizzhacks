"""Hot-swap XML scene programs by polling an HTTP backend endpoint.

Behavior:
1. Load environment via dotenv.
3. On startup, clear XML files in scenes/ and play default waiting scenes.
4. Poll POST /lesson/text/xml every 10 seconds.
5. If response XML bundle changed, replace scenes/ XML files and display them by
   StepTimeMain modulus buckets.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
import requests

from lightguide_client import LightGuideClient

SCENES_DIR = Path(
    os.environ.get(
        "LIGHTGUIDE_SCENES_DIR",
        r"C:\Program Files\OPS Solutions\Light Guide Systems\VDFPrograms\scenes",
    )
)


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


def _extract_xml_bundle_from_payload(payload: object) -> dict[str, str]:
    if isinstance(payload, str):
        payload = json.loads(payload)

    files: dict[str, str] = {}

    if isinstance(payload, list):
        for idx, item in enumerate(payload, start=1):
            if isinstance(item, str) and item.lstrip().startswith("<"):
                files[f"Scene{idx}.xml"] = item
            elif isinstance(item, dict):
                name = item.get("name") or item.get("filename")
                content = item.get("content") or item.get("xml")
                if isinstance(content, str):
                    if not isinstance(name, str) or not name.strip():
                        name = f"Scene{idx}.xml"
                    files[name] = content

    if isinstance(payload, dict):
        # FastAPI /lesson/text/xml current shape:
        # {
        #   "visualization_xml_documents": [{"path": "...", "xml": "<CommandInformation..."}],
        #   "tool_xml_documents": [{"path": "...", "xml": "<VisionProgramInformation..."}],
        #   ...
        # }
        vis_docs = payload.get("visualization_xml_documents")
        if isinstance(vis_docs, list):
            for idx, item in enumerate(vis_docs, start=1):
                if not isinstance(item, dict):
                    continue
                content = item.get("xml")
                if not isinstance(content, str):
                    continue
                name = item.get("name") or item.get("filename") or item.get("path")
                if not isinstance(name, str) or not name.strip():
                    name = f"Scene{idx}.xml"
                files[name] = content

        # Keep tool XML parsing for compatibility/debug payloads, but these are
        # not LightGuide VDFPrograms. We only include them if nothing better is present.
        if not files:
            tool_docs = payload.get("tool_xml_documents")
            if isinstance(tool_docs, list):
                for idx, item in enumerate(tool_docs, start=1):
                    if not isinstance(item, dict):
                        continue
                    content = item.get("xml")
                    if not isinstance(content, str):
                        continue
                    name = item.get("name") or item.get("filename") or item.get("path")
                    if not isinstance(name, str) or not name.strip():
                        name = f"ToolScene{idx}.xml"
                    files[name] = content

        scenes_map = payload.get("scenes")
        if isinstance(scenes_map, dict):
            for name, content in scenes_map.items():
                if isinstance(name, str) and isinstance(content, str):
                    files[name] = content

        xml_map = payload.get("xml_files")
        if isinstance(xml_map, dict):
            for name, content in xml_map.items():
                if isinstance(name, str) and isinstance(content, str):
                    files[name] = content

        xml_scenes = payload.get("xml_scenes")
        if isinstance(xml_scenes, list):
            for idx, item in enumerate(xml_scenes, start=1):
                if isinstance(item, str):
                    files[f"Scene{idx}.xml"] = item
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("filename") or f"Scene{idx}.xml"
                    content = item.get("content") or item.get("xml")
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
            content = payload.get("content") or payload.get("xml")
            if isinstance(name, str) and isinstance(content, str):
                files[name] = content

        if not files:
            inline_xml = payload.get("xml")
            if isinstance(inline_xml, str) and inline_xml.lstrip().startswith("<"):
                files["Scene1.xml"] = inline_xml

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


def _extract_xml_bundle_from_response(payload: Any) -> dict[str, str]:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.extend(
            [
                payload.get("data"),
                payload.get("result"),
                payload.get("payload"),
                payload.get("message"),
                payload.get("text"),
                payload.get("json"),
            ]
        )
    candidates.append(payload)

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return _extract_xml_bundle_from_payload(candidate)
        except Exception:
            continue

    raise ValueError("No XML bundle found in backend response")


def _build_scene_xmls_from_steps(lesson_name: str, steps: list[Any]) -> dict[str, str]:
    scene_docs: dict[str, str] = {}
    valid_steps = [step for step in steps if isinstance(step, dict)]
    for idx, step in enumerate(valid_steps, start=1):
        file_name = f"Scene{idx}.xml"
        scene_docs[file_name] = _build_scene_xml(lesson_name=lesson_name, step=step, scene_idx=idx)
    return scene_docs


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _rtf_text(text: str, font_size: int) -> str:
    clean = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return (
        r"{\rtf1\ansi\ansicpg1252\deff0\nouicompat\deflang1033{\fonttbl{\f0\fnil Microsoft Sans Serif;}}"
        + "\n"
        + r"{\colortbl ;\red255\green255\blue255;}"
        + "\n"
        + r"{\*\generator Riched20 10.0.19041}\viewkind4\uc1 "
        + "\n"
        + rf"\pard\cf1\f0\fs{max(font_size * 2, 2)} {clean}\par"
        + "\n}"
    )


def _build_scene_xml(*, lesson_name: str, step: dict[str, Any], scene_idx: int) -> str:
    root = ET.Element(
        "CommandInformation",
        {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns": "http://tempuri.org/CommandInformation.xsd",
        },
    )

    metadata = ET.SubElement(root, "Metadata")
    ET.SubElement(metadata, "SoftwareVersion").text = "25.3.4.0"
    ET.SubElement(metadata, "LicenseSerial").text = "833503"
    ET.SubElement(metadata, "Calibration").text = datetime.now().isoformat()
    ET.SubElement(metadata, "SaveCount").text = "1"
    ET.SubElement(metadata, "SaveDate").text = datetime.now().isoformat()

    line = 1

    def add_command(cmd_type: str, description: str, fields: dict[str, Any] | None = None) -> None:
        nonlocal line
        cmd = ET.SubElement(root, "Command")
        ET.SubElement(cmd, "Line").text = str(line)
        ET.SubElement(cmd, "Type").text = cmd_type
        ET.SubElement(cmd, "Description").text = description
        if fields:
            for key, value in fields.items():
                ET.SubElement(cmd, key).text = str(value)
        line += 1

    add_command("StartProgram", f"{lesson_name} scene {scene_idx}")
    add_command("StepStart", "Step Start", {"Comment": f"Scene {scene_idx}", "Step": 1})
    add_command("ClearCanvas", "Clear Canvas [All]", {"Canvas": 1024})

    visuals = step.get("visuals") if isinstance(step.get("visuals"), list) else []
    if visuals:
        for visual in visuals:
            if not isinstance(visual, dict):
                continue
            visual_type = str(visual.get("type") or "").strip().lower()
            if visual_type == "text":
                text = str(visual.get("text") or step.get("instruction") or f"Scene {scene_idx}")
                x = _to_int(visual.get("x"), 780)
                y = _to_int(visual.get("y"), 280)
                width = _to_int(visual.get("width"), 400)
                height = _to_int(visual.get("height"), 70)
                font_size = _to_int(visual.get("font_size"), 36)
                add_command(
                    "VDFText",
                    f'"{text}"',
                    {
                        "Text": text,
                        "Canvas": 1,
                        "X": x,
                        "Y": y,
                        "Width": width,
                        "Height": height,
                        "BlinkType": "None",
                        "BlinkRate": 1000,
                        "Movements": "None",
                        "FontName": "Microsoft Sans Serif",
                        "TextColor": "255,255,255,255",
                        "FontSize": font_size,
                        "Justify": 0,
                        "Rtf": _rtf_text(text, font_size),
                    },
                )
            elif visual_type in {"graphics", "vdfgraphics"}:
                filename = str(visual.get("filename") or "Square Outline.svg")
                x = _to_int(visual.get("x"), 840)
                y = _to_int(visual.get("y"), 380)
                width = _to_int(visual.get("width"), 120)
                height = _to_int(visual.get("height"), 220)
                color = str(visual.get("color") or "0,255,0")
                add_command(
                    "VDFGraphics",
                    f"{filename}; Color: '{color}'",
                    {
                        "FileName": filename,
                        "Canvas": 1,
                        "X": x,
                        "Y": y,
                        "Width": width,
                        "Height": height,
                        "BlinkRate": 1000,
                        "Movements": "None",
                        "FilePath": (
                            "C:\\Program Files\\OPS Solutions\\Light Guide Systems\\"
                            f"VDFGraphics\\Shapes\\{filename}"
                        ),
                        "FilterColor": color,
                    },
                )

    if line == 4:
        fallback = str(step.get("instruction") or step.get("description") or f"Scene {scene_idx}")
        add_command(
            "VDFText",
            f'"{fallback}"',
            {
                "Text": fallback,
                "Canvas": 1,
                "X": 780,
                "Y": 300,
                "Width": 600,
                "Height": 70,
                "BlinkType": "None",
                "BlinkRate": 1000,
                "Movements": "None",
                "FontName": "Microsoft Sans Serif",
                "TextColor": "255,255,255,255",
                "FontSize": 36,
                "Justify": 0,
                "Rtf": _rtf_text(fallback, 36),
            },
        )

    add_command(
        "EndProgram",
        f"End Scene {scene_idx}",
        {
            "FileName": f"Scene{scene_idx}.xml",
            "FilePath": (
                "C:\\Program Files\\OPS Solutions\\Light Guide Systems\\"
                f"VDFPrograms\\scenes\\Scene{scene_idx}.xml"
            ),
        },
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _write_scene_bundle(scenes_dir: Path, files: dict[str, str]) -> list[str]:
    _clear_scene_xmls(scenes_dir)

    written: list[str] = []
    for file_name in sorted(files.keys()):
        target = scenes_dir / file_name
        target.write_text(files[file_name], encoding="utf-8")
        written.append(f"scenes/{file_name}")
    return written


def _post_lesson_xml(endpoint_url: str, query: str, provider: str, timeout_seconds: float) -> Any:
    payload = {"query": query, "provider": provider}
    response = requests.post(endpoint_url, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


async def _endpoint_poller(
    *,
    endpoint_url: str,
    query: str,
    provider: str,
    scenes_dir: Path,
    updates: asyncio.Queue[SceneSet],
    request_timeout_seconds: float,
    poll_seconds: float,
) -> None:
    version = 0
    last_signature: str | None = None

    while True:
        try:
            response_payload = await asyncio.to_thread(
                _post_lesson_xml,
                endpoint_url,
                query,
                provider,
                request_timeout_seconds,
            )
            files = _extract_xml_bundle_from_response(response_payload)
            signature = json.dumps(files, sort_keys=True)

            if signature != last_signature:
                programs = _write_scene_bundle(scenes_dir, files)
                version += 1
                last_signature = signature
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
        description="Swap XML programs from backend endpoint using StepTimeMain modulus",
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
        "--backend-poll-seconds",
        type=float,
        default=10.0,
        help="Polling interval for /lesson/text/xml updates",
    )
    parser.add_argument(
        "--endpoint-url",
        default="https://7a26-141-210-86-11.ngrok-free.app/lesson/text/xml",
        help="Backend endpoint that returns XML files",
    )
    parser.add_argument(
        "--lesson-query",
        default="Create a 3-step lesson for wiring an LED with ESP32",
        help="Query sent in POST body to backend",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="Provider sent in POST body to backend",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout for backend request",
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

    scenes_dir = SCENES_DIR

    _clear_scene_xmls(scenes_dir)

    default_programs = args.default_programs or ["default/Waiting1.xml", "default/Waiting2.xml"]

    updates: asyncio.Queue[SceneSet] = asyncio.Queue()

    poller_task = asyncio.create_task(
        _endpoint_poller(
            endpoint_url=args.endpoint_url,
            query=args.lesson_query,
            provider=args.provider,
            scenes_dir=scenes_dir,
            updates=updates,
            request_timeout_seconds=args.request_timeout_seconds,
            poll_seconds=args.backend_poll_seconds,
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
