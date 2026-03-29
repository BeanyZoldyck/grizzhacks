"""Generate lesson steps from AI prompt and optionally persist to MongoDB.

Usage:
    python ai_lesson.py --query "Create a 3-step lesson for wiring an LED with ESP32"
    python ai_lesson.py --from-file lesson.json   # skip AI; same JSON shape as generated output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mongo"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

from coordinate_transform import viz_to_tool
from lesson_cloud import send_lesson_to_mongodb
from websocket_client import load_env

load_env()

SYSTEM_PROMPT = """You are an expert in creating embedded systems lesson content.

Generate lesson steps in JSON format with this structure:
{
  "lesson_name": "Descriptive_Lesson_Name",
  "description": "Brief description of the lesson",
  "steps": [
    {
      "step": 1,
      "description": "Short description of this step",
      "instruction": "Clear user instruction text (what they should do)",
      "visuals": [
        {
          "type": "Text|Graphics|Line",
          "text": "Text to display (for Text)",
          "filename": "ShapeFile.svg (for Graphics)",
          "x": 500,
          "y": 100,
          "width": 200,
          "height": 50,
          "font_size": 20,
          "color": "R,G,B (e.g., 0,255,0 for green)"
        }
      ]
    }
  ]
}

Visual types:
- Text: Text overlay (text, x, y, width, height, font_size)
- Graphics: Shapes (filename, x, y, width, height, color)
- Line: Lines (x, y, width, height, color)

Coordinates: 0-1024 range. Colors: RGB format (0,255,0).

Return ONLY valid JSON, no markdown, no explanations."""


def _tool_xml_value(parent: ET.Element, key: str, value: Any) -> None:
    ET.SubElement(parent, key).text = str(value)


def _build_tool_box_vertices(
    x_viz: float,
    y_viz: float,
    width_viz: float,
    height_viz: float,
) -> list[tuple[int, int]]:
    x1_tool, y1_tool = viz_to_tool(x_viz, y_viz)
    x2_tool, y2_tool = viz_to_tool(x_viz + width_viz, y_viz + height_viz)
    x_min = int(round(min(x1_tool, x2_tool)))
    x_max = int(round(max(x1_tool, x2_tool)))
    y_min = int(round(min(y1_tool, y2_tool)))
    y_max = int(round(max(y1_tool, y2_tool)))
    return [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]


def _build_tool_xml_for_step(step: dict[str, Any], *, step_number: int) -> ET.Element:
    root = ET.Element(
        "VisionProgramInformation",
        {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        },
    )
    ET.SubElement(root, "Erode")
    ET.SubElement(root, "Dilate")
    flip_image = ET.SubElement(root, "FlipImage")
    _tool_xml_value(flip_image, "ID", 0)
    ET.SubElement(root, "BaseLine")
    config = ET.SubElement(root, "Configuration")
    _tool_xml_value(config, "SchemaVersion", "1.3")
    _tool_xml_value(config, "SaveDate", datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))

    visuals = step.get("visuals")
    if not isinstance(visuals, list):
        visuals = []

    tool_index = 1
    for visual in visuals:
        if not isinstance(visual, dict):
            continue
        visual_type = str(visual.get("type", "")).strip()
        if visual_type not in {"Graphics", "VDFGraphics"}:
            continue
        try:
            x = float(visual["x"])
            y = float(visual["y"])
            width = float(visual["width"])
            height = float(visual["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue

        vertices = _build_tool_box_vertices(x, y, width, height)
        tool = ET.SubElement(root, "Tool")
        _tool_xml_value(tool, "ToolName", f"Tool{tool_index:02d}")
        _tool_xml_value(tool, "ToolType", "Brightness")
        _tool_xml_value(tool, "UseOriginalImage", "false")

        filters = ET.SubElement(tool, "Filters")
        filters.set("{http://www.w3.org/2001/XMLSchema-instance}type", "RGB")
        color_min = ET.SubElement(filters, "ColorMin")
        color_min.set("{http://www.w3.org/2001/XMLSchema-instance}type", "xsd:string")
        color_min.text = "Black"
        color_max = ET.SubElement(filters, "ColorMax")
        color_max.set("{http://www.w3.org/2001/XMLSchema-instance}type", "xsd:string")
        color_max.text = "Red"

        region = ET.SubElement(tool, "Region")
        for vx, vy in vertices:
            vertex = ET.SubElement(region, "Vertex")
            _tool_xml_value(vertex, "X", vx)
            _tool_xml_value(vertex, "Y", vy)
        origin_offset = ET.SubElement(region, "OriginOffset")
        _tool_xml_value(origin_offset, "X", 0)
        _tool_xml_value(origin_offset, "Y", 0)

        ET.SubElement(tool, "XLink")
        ET.SubElement(tool, "YLink")
        ET.SubElement(tool, "AngleLink")
        _tool_xml_value(tool, "ExcludeFromTrueList", "false")
        _tool_xml_value(tool, "ImageBasedOrigin", "true")
        _tool_xml_value(tool, "CenterResult", "true")
        _tool_xml_value(tool, "ThoroughSearch", "false")

        for key, value in (("ThresholdMin", 29), ("ThresholdMax", 255)):
            inputs = ET.SubElement(tool, "Inputs")
            _tool_xml_value(inputs, "Key", key)
            val = ET.SubElement(inputs, "Value")
            val.set("{http://www.w3.org/2001/XMLSchema-instance}type", "xsd:int")
            val.text = str(value)

        for key, enabled in (("InRange", "true"), ("Count", "false"), ("Avg", "false")):
            outputs = ET.SubElement(tool, "Outputs")
            _tool_xml_value(outputs, "Key", key)
            _tool_xml_value(outputs, "Enabled", enabled)

        tool_index += 1

    camera = ET.SubElement(root, "Camera")
    _tool_xml_value(camera, "CameraType", "WEBCAM")
    video_mode = ET.SubElement(camera, "VideoMode")
    _tool_xml_value(video_mode, "Sensor", "COLOR")
    _tool_xml_value(video_mode, "Width", 1104)
    _tool_xml_value(video_mode, "Height", 828)
    _tool_xml_value(video_mode, "FrameRate", 10)
    _tool_xml_value(video_mode, "PixelFormat", -1)
    _tool_xml_value(video_mode, "SensorMode", -1)
    _tool_xml_value(video_mode, "X", 0)
    _tool_xml_value(video_mode, "Y", 0)
    _tool_xml_value(camera, "DevicePath", "")
    ET.SubElement(camera, "BackupIdentifier")
    _tool_xml_value(camera, "Name", f"Generated Camera Step {step_number}")
    _tool_xml_value(camera, "Alias", "Camera1")
    _tool_xml_value(camera, "RangeMin", -1)
    _tool_xml_value(camera, "RangeMax", -1)
    return root


def save_tool_xml_files(
    lesson_name: str,
    steps: list[dict[str, Any]],
    output_dir: str,
) -> list[dict[str, Any]]:
    """Generate one optical-tool XML per step from lesson visual boxes.

    Returns artifact descriptors that include file path and XML content.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lesson_slug = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in lesson_name.strip()
    ) or "Generated_Lesson"
    artifacts: list[dict[str, Any]] = []

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        root = _build_tool_xml_for_step(step, step_number=idx)
        if not root.findall("Tool"):
            continue

        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ")
        except AttributeError:
            pass
        out_path = out_dir / f"{lesson_slug}_step_{idx:02d}_tool.xml"
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
        # Parse back after write to verify this is valid XML and has expected shape.
        parsed_root = ET.parse(out_path).getroot()
        if parsed_root.tag != "VisionProgramInformation":
            raise RuntimeError(f"Invalid tool XML root in {out_path}")
        if not parsed_root.findall("Tool"):
            raise RuntimeError(f"Tool XML missing <Tool> entries in {out_path}")

        artifacts.append(
            {
                "step": idx,
                "path": out_path,
                "xml": out_path.read_text(encoding="utf-8"),
            }
        )
    return artifacts


def generate_lesson_with_openai(
    query: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Generate lesson steps using OpenAI API."""
    try:
        import httpx
    except ImportError as e:
        raise ImportError(
            "httpx package not installed. Run: pip install httpx",
        ) from e

    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")

    resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    if not resolved_base_url:
        resolved_base_url = "https://api.openai.com/v1/chat/completions"
    elif not resolved_base_url.startswith(
        "http://"
    ) and not resolved_base_url.startswith("https://"):
        resolved_base_url = "https://" + resolved_base_url

    resolved_model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "temperature": 0.7,
    }

    response = httpx.post(
        resolved_base_url,
        headers=headers,
        json=payload,
        timeout=60.0,
    )

    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {content}") from e


def generate_lesson_with_anthropic(
    query: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Generate lesson steps using Anthropic API."""
    try:
        import anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic package not installed. Run: pip install anthropic",
        ) from e

    client_kwargs = {"api_key": api_key or os.environ.get("ANTHROPIC_API_KEY")}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    response = client.messages.create(
        model=model or os.environ.get("ANTHROPIC_MODEL") or "MiniMax-M2.7",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": query},
        ],
    )

    # Thinking-enabled models may return ThinkingBlock before TextBlock; only TextBlock has .text
    text_parts: list[str] = []
    for block in response.content:
        fragment = getattr(block, "text", None)
        if fragment:
            text_parts.append(fragment)
    content = "".join(text_parts).strip()
    if not content:
        raise ValueError(
            "Anthropic response had no text blocks (only thinking/tool blocks?). "
            "Try a model without extended thinking or adjust the API response."
        )

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {content}") from e


def generate_lesson(
    query: str,
    *,
    provider: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Generate lesson JSON from a text prompt (OpenAI or Anthropic)."""
    if provider == "openai":
        return generate_lesson_with_openai(query, api_key, base_url, model)
    if provider == "anthropic":
        return generate_lesson_with_anthropic(query, api_key, base_url, model)
    raise ValueError(f"Unknown provider: {provider!r} (use 'openai' or 'anthropic')")


async def send_lesson(
    lesson_name: str,
    steps: list[dict],
    *,
    verbose: bool = True,
    enable_cloud: bool | None = None,
    description: str | None = None,
    source: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Persist lesson to MongoDB when enabled (see LESSON_CLOUD)."""
    return await send_lesson_to_mongodb(
        lesson_name,
        steps,
        description=description,
        source=source,
        metadata=metadata,
        enable_cloud=enable_cloud,
        verbose=verbose,
    )


def _load_lesson_json(path: str) -> dict:
    """Load lesson dict from JSON file; raises FileNotFoundError / json.JSONDecodeError."""
    raw = Path(path).read_text()
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate lesson with AI and optionally persist to MongoDB",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--query",
        "-q",
        help="Lesson prompt (e.g., 'Create a 3-step lesson for wiring an LED')",
    )
    input_group.add_argument(
        "--from-file",
        metavar="PATH",
        help="Load lesson JSON from file instead of calling the AI",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["openai", "anthropic"],
        help="AI provider (default: anthropic)",
    )
    parser.add_argument(
        "--api-key",
        help="API key (or set OPENAI_API_KEY/ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--base-url",
        help="API base URL (OPENAI_BASE_URL or ANTHROPIC_BASE_URL env var)",
    )
    parser.add_argument(
        "--model",
        help="Model name (OPENAI_MODEL or ANTHROPIC_MODEL env var, default: gpt-4o-mini for OpenAI, MiniMax-M2.7 for Anthropic)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate lesson but don't write to MongoDB",
    )
    parser.add_argument(
        "--no-cloud",
        action="store_true",
        help="Skip MongoDB insert. Overrides LESSON_CLOUD.",
    )
    parser.add_argument(
        "--save-json",
        help="Save generated lesson JSON to file",
    )
    parser.add_argument(
        "--save-tool-xml-dir",
        help="Directory to write optical tool XML files (one per step)",
    )
    args = parser.parse_args()

    lesson_data: dict
    if args.from_file:
        try:
            lesson_data = _load_lesson_json(args.from_file)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {args.from_file}: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(lesson_data, dict):
            print("Error: lesson file must be a JSON object", file=sys.stderr)
            sys.exit(1)
        steps = lesson_data.get("steps")
        if not isinstance(steps, list) or not steps:
            print(
                "Error: lesson JSON must contain a non-empty 'steps' array",
                file=sys.stderr,
            )
            sys.exit(1)
        origin = "file"
    else:
        if args.api_key:
            api_key = args.api_key
        elif args.provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        else:
            api_key = os.environ.get("OPENAI_API_KEY")

        if args.provider == "openai":
            base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
            model = args.model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        else:
            base_url = args.base_url or os.environ.get("ANTHROPIC_BASE_URL")
            model = args.model or os.environ.get("ANTHROPIC_MODEL") or "MiniMax-M2.7"

        print("Configuration:")
        print(f"  Provider: {args.provider}")
        print(f"  API Key: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
        if base_url:
            print(f"  Base URL: {base_url}")
            print(f"  Note: Base URL used as-is (no path appended)")
        elif args.provider == "openai":
            print(f"  Base URL: default (https://api.openai.com/v1/chat/completions)")
        elif args.provider == "anthropic":
            print(f"  Base URL: default (Anthropic)")
        print(f"  Model: {model}")
        q = args.query or ""
        print(f"  Query: {q[:60]}{'...' if len(q) > 60 else ''}")
        print()

        print(f"Generating lesson with {args.provider}...")
        try:
            lesson_data = generate_lesson(
                args.query,
                provider=args.provider,
                api_key=args.api_key,
                base_url=args.base_url,
                model=args.model,
            )
        except (ImportError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        origin = "generated"

    lesson_name = lesson_data.get("lesson_name", "Generated_Lesson")
    steps = lesson_data["steps"]

    if origin == "file":
        print(f"✓ Loaded lesson from {args.from_file}: {lesson_name}")
    else:
        print(f"✓ Generated lesson: {lesson_name}")
    print(f"✓ {len(steps)} steps")

    tool_xml_artifacts: list[dict[str, Any]] = []

    if args.save_tool_xml_dir:
        tool_xml_artifacts = save_tool_xml_files(lesson_name, steps, args.save_tool_xml_dir)
        if tool_xml_artifacts:
            tool_paths = [str(a["path"]) for a in tool_xml_artifacts]
            lesson_data["tool_xml_files"] = tool_paths
            lesson_data["tool_xml_documents"] = [
                {
                    "step": a["step"],
                    "path": str(a["path"]),
                    "xml": a["xml"],
                }
                for a in tool_xml_artifacts
            ]
            print(
                f"✓ Saved {len(tool_xml_artifacts)} tool XML file(s) to {args.save_tool_xml_dir}"
            )
            for tool_path in tool_paths:
                print(f"  - {tool_path}")
        else:
            print(
                "⚠ No tool XML files were generated (no Graphics visuals with valid box dimensions)."
            )

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(lesson_data, f, indent=2)
        print(f"✓ Saved JSON to {args.save_json}")

    if args.dry_run:
        print("\n--- Dry Run: lesson JSON ---")
        preview = json.dumps(lesson_data, indent=2)
        print(preview[:2000])
        if len(preview) > 2000:
            print(f"\n... ({len(preview)} total characters)")
    else:
        try:
            asyncio.run(
                send_lesson(
                    lesson_name,
                    steps,
                    enable_cloud=not args.no_cloud,
                    description=lesson_data.get("description"),
                    source="ai_lesson",
                    metadata={
                        "tool_xml_documents": [
                            {
                                "step": a["step"],
                                "path": str(a["path"]),
                                "xml": a["xml"],
                            }
                            for a in tool_xml_artifacts
                        ]
                    }
                    if tool_xml_artifacts
                    else None,
                )
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
