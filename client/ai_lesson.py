"""Generate lesson steps from AI prompt and optionally persist to MongoDB.

Usage:
    python ai_lesson.py --query "Create a 3-step lesson for wiring an LED with ESP32"
    python ai_lesson.py --from-file lesson.json   # skip AI; same JSON shape as generated output
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class FirmwareStep:
    """Compact firmware-ready lesson step."""

    step: int
    description: str
    instruction: str


def _escape_cpp_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _to_firmware_steps(steps: list[dict[str, Any]]) -> list[FirmwareStep]:
    firmware_steps: list[FirmwareStep] = []
    for idx, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        step_num = raw_step.get("step")
        if not isinstance(step_num, int):
            step_num = idx
        description = str(raw_step.get("description", "")).strip() or f"Step {step_num}"
        instruction = str(raw_step.get("instruction", "")).strip()
        firmware_steps.append(
            FirmwareStep(
                step=step_num,
                description=description,
                instruction=instruction,
            ),
        )
    return firmware_steps


def _render_esp32_firmware_source(
    *,
    lesson_name: str,
    steps: list[FirmwareStep],
) -> str:
    escaped_lesson_name = _escape_cpp_string(lesson_name)
    step_count = len(steps)
    step_initializers = ",\n".join(
        f'  {{{s.step}, "{_escape_cpp_string(s.description)}", "{_escape_cpp_string(s.instruction)}"}}'
        for s in steps
    )
    if not step_initializers:
        step_initializers = '  {1, "No generated steps", ""}'

    return f"""#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"

struct LessonStep {{
  int number;
  const char* description;
  const char* instruction;
}};

static const char* LESSON_NAME = "{escaped_lesson_name}";
static const LessonStep LESSON_STEPS[] = {{
{step_initializers}
}};
static const size_t LESSON_STEP_COUNT = sizeof(LESSON_STEPS) / sizeof(LESSON_STEPS[0]);

size_t currentStepIndex = 0;
unsigned long lastPing = 0;

void connectWiFi() {{
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("Connecting to Wi-Fi '%s'...\\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {{
    delay(500);
    Serial.print('.');
    if (millis() - start > 20000) {{
      Serial.println("\\nFailed to connect within 20s");
      return;
    }}
  }}
  Serial.println();
  Serial.printf("Connected, IP: %s\\n", WiFi.localIP().toString().c_str());
}}

String getDeviceId() {{
  uint64_t mac = ESP.getEfuseMac();
  char buf[32];
  sprintf(buf, "%012llX", mac);
  return String(buf);
}}

String buildPayload(const LessonStep& step) {{
  String payload = "{{";
  payload += "\\"msg\\":\\"lesson_step\\",";
  payload += "\\"device\\":\\"esp32c3\\",";
  payload += "\\"id\\":\\"" + getDeviceId() + "\\",";
  payload += "\\"lesson\\":\\"" + String(LESSON_NAME) + "\\",";
  payload += "\\"step\\":" + String(step.number) + ",";
  payload += "\\"step_description\\":\\"" + String(step.description) + "\\",";
  payload += "\\"instruction\\":\\"" + String(step.instruction) + "\\"";
  payload += "}}";
  return payload;
}}

void sendLessonStepPing() {{
  if (WiFi.status() != WL_CONNECTED) {{
    Serial.println("Not connected to Wi-Fi, skipping ping");
    return;
  }}

  if (LESSON_STEP_COUNT == 0) {{
    Serial.println("No lesson steps available");
    return;
  }}

  const LessonStep& step = LESSON_STEPS[currentStepIndex];
  HTTPClient http;
  http.begin(SERVER_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  String payload = buildPayload(step);
  int httpCode = http.POST(payload);
  if (httpCode > 0) {{
    String resp = http.getString();
    Serial.printf(
      "STEP %d/%d -> code: %d resp: %s\\n",
      step.number,
      (int)LESSON_STEP_COUNT,
      httpCode,
      resp.c_str()
    );
    currentStepIndex = (currentStepIndex + 1) % LESSON_STEP_COUNT;
  }} else {{
    Serial.printf("STEP ping failed, error: %s\\n", http.errorToString(httpCode).c_str());
  }}
  http.end();
}}

void setup() {{
  Serial.begin(115200);
  delay(1000);
  Serial.printf(
    "ESP32-C3 lesson firmware starting (lesson: %s, steps: %d)\\n",
    LESSON_NAME,
    (int)LESSON_STEP_COUNT
  );
  connectWiFi();
}}

void loop() {{
  if (WiFi.status() != WL_CONNECTED) {{
    connectWiFi();
  }}

  unsigned long now = millis();
  if (now - lastPing >= PING_INTERVAL_MS) {{
    lastPing = now;
    sendLessonStepPing();
  }}
  delay(100);
}}
"""


def write_lesson_firmware(
    *,
    project_dir: str | Path,
    lesson_name: str,
    steps: list[dict[str, Any]],
    main_rel_path: str = "src/main.cpp",
) -> Path:
    """Render lesson-driven firmware and write it into the PlatformIO project."""
    resolved_project_dir = Path(project_dir).resolve()
    ini_path = resolved_project_dir / "platformio.ini"
    if not ini_path.exists():
        raise RuntimeError(
            f"platformio.ini not found at {ini_path}. "
            "Set --platformio-project-dir to your firmware project root.",
        )

    main_path = resolved_project_dir / Path(main_rel_path)
    main_path.parent.mkdir(parents=True, exist_ok=True)
    firmware_source = _render_esp32_firmware_source(
        lesson_name=lesson_name,
        steps=_to_firmware_steps(steps),
    )
    main_path.write_text(firmware_source, encoding="utf-8")
    return main_path


def generate_slideshow_pdf_from_lesson(
    *,
    lesson_data: dict[str, Any],
    output_pdf: str | Path,
) -> Path:
    """Generate slideshow PDF using slideshow-generator modules."""
    slideshow_dir = _ROOT / "slideshow-generator"
    if not slideshow_dir.exists():
        raise RuntimeError(
            f"slideshow-generator directory not found at {slideshow_dir}",
        )

    sys.path.insert(0, str(slideshow_dir))
    try:
        from lesson_parser import LessonParser
        from pdf_generator import PDFGenerator
    except ImportError as e:
        raise RuntimeError(
            "Failed to import slideshow generator dependencies. "
            "Install them with: pip install -r slideshow-generator/requirements.txt",
        ) from e

    lesson_parser = LessonParser(lesson_data=lesson_data)
    if not lesson_parser.validate():
        raise RuntimeError("Invalid lesson data structure for slideshow generation")

    output_path = Path(output_pdf).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator = PDFGenerator(str(output_path), lesson_parser)
    generator.generate()
    return output_path


def _default_slideshow_output_path(lesson_name: str) -> Path:
    lesson_slug = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in lesson_name.strip()
    ) or "Generated_Lesson"
    return (_ROOT / "slides" / f"{lesson_slug}.pdf")


def _resolve_platformio_command(explicit_cmd: str | None = None) -> str:
    """Resolve a runnable PlatformIO command."""
    if explicit_cmd:
        return explicit_cmd

    env_cmd = os.environ.get("PLATFORMIO_CMD")
    if env_cmd:
        return env_cmd

    # Common command names. VSCode PlatformIO users may still need PLATFORMIO_CMD
    # if the extension's bundled executable is not on PATH.
    for candidate in ("platformio", "pio"):
        if shutil.which(candidate):
            return candidate

    raise RuntimeError(
        "PlatformIO command not found. Install platformio CLI, ensure `platformio`/`pio` "
        "is on PATH, or set PLATFORMIO_CMD to the executable path.",
    )


def flash_hardware_with_platformio(
    *,
    project_dir: str | Path,
    environment: str,
    platformio_cmd: str | None = None,
) -> None:
    """Flash connected hardware via PlatformIO upload target."""
    resolved_project_dir = Path(project_dir).resolve()
    ini_path = resolved_project_dir / "platformio.ini"
    if not ini_path.exists():
        raise RuntimeError(
            f"platformio.ini not found at {ini_path}. "
            "Set --platformio-project-dir to your firmware project root.",
        )

    cmd = [
        _resolve_platformio_command(platformio_cmd),
        "run",
        "-e",
        environment,
        "-t",
        "upload",
    ]
    print(
        f"\nFlashing hardware with PlatformIO (env: {environment}) in {resolved_project_dir}...",
    )
    print("Command:", " ".join(cmd))

    # Stream output directly so upload progress is visible.
    result = subprocess.run(
        cmd,
        cwd=str(resolved_project_dir),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"PlatformIO upload failed with exit code {result.returncode}",
        )
    print("✓ Hardware flash completed")


def _tool_xml_value(parent: ET.Element, key: str, value: Any) -> None:
    ET.SubElement(parent, key).text = str(value)


def _visual_command(
    root: ET.Element,
    line: int,
    command_type: str,
    description: str,
    extra: dict[str, Any] | None = None,
) -> int:
    command = ET.SubElement(root, "Command")
    _tool_xml_value(command, "Line", line)
    _tool_xml_value(command, "Type", command_type)
    _tool_xml_value(command, "Description", description)
    for key, value in (extra or {}).items():
        _tool_xml_value(command, key, value)
    return line + 1


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rgb_to_rgba(color: str) -> str:
    parts = [p.strip() for p in str(color).split(",")]
    if len(parts) != 3:
        return "255,255,255,255"
    try:
        rgb = [max(0, min(255, int(float(p)))) for p in parts]
    except ValueError:
        return "255,255,255,255"
    return f"{rgb[0]},{rgb[1]},{rgb[2]},255"


def _build_visualization_program_xml(
    lesson_name: str,
    steps: list[dict[str, Any]],
) -> ET.Element:
    root = ET.Element(
        "CommandInformation",
        {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns": "http://tempuri.org/CommandInformation.xsd",
        },
    )
    metadata = ET.SubElement(root, "Metadata")
    _tool_xml_value(metadata, "SoftwareVersion", "25.3.4.0")
    _tool_xml_value(metadata, "LicenseSerial", "000000")
    _tool_xml_value(metadata, "SaveDate", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

    line = 1
    line = _visual_command(root, line, "StartProgram", f"{lesson_name} workflow")

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue

        step_num = step.get("step")
        if not isinstance(step_num, int):
            step_num = idx
        step_desc = str(step.get("description") or f"Step {step_num}").strip()

        line = _visual_command(
            root,
            line,
            "StepStart",
            "Step Start",
            {"Comment": step_desc, "Step": step_num},
        )
        line = _visual_command(
            root,
            line,
            "ClearCanvas",
            "Clear Canvas [All]",
            {"Canvas": 1024},
        )

        visuals = step.get("visuals")
        if not isinstance(visuals, list):
            visuals = []

        for visual in visuals:
            if not isinstance(visual, dict):
                continue
            visual_type = str(visual.get("type", "")).strip()

            x = _as_float(visual.get("x"))
            y = _as_float(visual.get("y"))
            width = _as_float(visual.get("width"))
            height = _as_float(visual.get("height"))
            if x is None or y is None or width is None or height is None:
                continue

            if visual_type in {"Text", "VDFText"}:
                text = str(visual.get("text") or "").strip()
                if not text:
                    continue
                font_size = int(_as_float(visual.get("font_size")) or 24)
                text_color = _rgb_to_rgba(str(visual.get("color") or "255,255,255"))
                line = _visual_command(
                    root,
                    line,
                    "VDFText",
                    f'"{text}"',
                    {
                        "Text": text,
                        "Canvas": 1,
                        "X": x,
                        "Y": y,
                        "Width": max(1, width),
                        "Height": max(1, height),
                        "BlinkType": "None",
                        "BlinkRate": 1000,
                        "Movements": "None",
                        "FontName": "Microsoft Sans Serif",
                        "TextColor": text_color,
                        "FontSize": max(6, font_size),
                        "Justify": 0,
                    },
                )
                continue

            if visual_type in {"Graphics", "VDFGraphics", "Line"}:
                file_name = str(
                    visual.get("filename")
                    or ("Line.svg" if visual_type == "Line" else "Square Outline.svg")
                ).strip()
                if not file_name:
                    file_name = "Square Outline.svg"
                filter_color = str(visual.get("color") or "0,255,0")
                line = _visual_command(
                    root,
                    line,
                    "VDFGraphics",
                    f"{file_name}; Color: {filter_color}",
                    {
                        "FileName": file_name,
                        "Canvas": 1,
                        "X": x,
                        "Y": y,
                        "Width": max(1, width),
                        "Height": max(1, height),
                        "BlinkRate": 1000,
                        "Movements": "None",
                        "FilePath": (
                            r"C:\Program Files\OPS Solutions\Light Guide Systems\VDFGraphics\Shapes"
                            f"\\{file_name}"
                        ),
                        "FilterColor": filter_color,
                    },
                )

        line = _visual_command(
            root,
            line,
            "Confirmation",
            "Wait For [Manual Confirmation]",
            {
                "Variable": "Manual Confirmation",
                "ConfirmType": "Forward",
                "StepsToMove": 1,
            },
        )

    line = _visual_command(
        root,
        line,
        "EndProgram",
        "End of Workflow",
        {
            "FileName": f"{lesson_name}.xml",
            "FilePath": (
                r"C:\Program Files\OPS Solutions\Light Guide Systems\VDFPrograms"
                f"\\{lesson_name}.xml"
            ),
        },
    )
    return root


def save_visualization_xml_files(
    lesson_name: str,
    steps: list[dict[str, Any]],
    output_dir: str,
) -> list[dict[str, Any]]:
    """Generate one visualization program XML that contains all lesson steps."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lesson_slug = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in lesson_name.strip()
    ) or "Generated_Lesson"

    root = _build_visualization_program_xml(lesson_slug, steps)
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass

    out_path = out_dir / f"{lesson_slug}_visualization.xml"
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

    parsed_root = ET.parse(out_path).getroot()
    if not parsed_root.tag.endswith("CommandInformation"):
        raise RuntimeError(f"Invalid visualization XML root in {out_path}")

    return [
        {
            "path": out_path,
            "xml": out_path.read_text(encoding="utf-8"),
        }
    ]


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

    def _normalize_openai_endpoint(url: str) -> str:
        normalized = url.strip().rstrip("/")
        if not normalized:
            return "https://api.openai.com/v1/chat/completions"
        if not normalized.startswith("http://") and not normalized.startswith("https://"):
            normalized = "https://" + normalized
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return normalized + "/chat/completions"
        return normalized

    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")

    resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    if not resolved_base_url:
        resolved_base_url = "https://api.openai.com/v1/chat/completions"
    resolved_base_url = _normalize_openai_endpoint(resolved_base_url)

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

    try:
        response = httpx.post(
            resolved_base_url,
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        hint = ""
        if "minimax" in resolved_base_url and "/chat/completions" not in resolved_base_url:
            hint = (
                " Hint: OPENAI-compatible endpoints usually require "
                "'.../v1/chat/completions', not just '.../v1'."
            )
        raise ValueError(
            f"OpenAI-compatible request failed ({e.response.status_code}) at "
            f"{resolved_base_url}: {e.response.text[:300]}{hint}",
        ) from e
    except httpx.HTTPError as e:
        raise ValueError(
            f"OpenAI-compatible request error at {resolved_base_url}: {e!s}",
        ) from e

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
    parser.add_argument(
        "--flash-hardware",
        action="store_true",
        help="After lesson processing, flash firmware with PlatformIO upload target",
    )
    parser.add_argument(
        "--platformio-env",
        default=os.environ.get("PLATFORMIO_ENV", "esp32-c3"),
        help="PlatformIO environment to upload (default: PLATFORMIO_ENV or esp32-c3)",
    )
    parser.add_argument(
        "--platformio-project-dir",
        default=str(_ROOT),
        help="PlatformIO project root containing platformio.ini (default: repo root)",
    )
    parser.add_argument(
        "--platformio-cmd",
        default=os.environ.get("PLATFORMIO_CMD"),
        help="PlatformIO executable/command (default: PLATFORMIO_CMD or auto-detect)",
    )
    parser.add_argument(
        "--write-firmware",
        action="store_true",
        help="Write generated ESP32 firmware from lesson steps before optional flashing",
    )
    parser.add_argument(
        "--firmware-main-path",
        default=os.environ.get("FIRMWARE_MAIN_PATH", "src/main.cpp"),
        help="Path (relative to --platformio-project-dir) for generated firmware source",
    )
    parser.add_argument(
        "--generate-slideshow",
        action="store_true",
        help="Generate lesson slideshow PDF using slideshow-generator",
    )
    parser.add_argument(
        "--slideshow-output",
        help="Output PDF path for --generate-slideshow (default: ./slides/<lesson_name>.pdf)",
    )
    parser.add_argument(
        "--open-slideshow",
        action="store_true",
        help="Open generated slideshow PDF after XML generation is complete",
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
            print(
                "  Note: OpenAI-compatible URLs ending in /v1 are normalized to /v1/chat/completions"
            )
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
    slideshow_output_path: Path | None = None
    slideshow_future: concurrent.futures.Future[Path] | None = None
    slideshow_executor: concurrent.futures.ThreadPoolExecutor | None = None

    if args.generate_slideshow:
        slideshow_output = args.slideshow_output or str(
            _default_slideshow_output_path(lesson_name)
        )
        slideshow_output_path = Path(slideshow_output).expanduser().resolve()

        # Run slideshow generation in background when XML generation is requested.
        # XML is higher priority and runs on the main thread.
        if args.save_tool_xml_dir:
            print(
                "Starting slideshow PDF generation in background while prioritizing XML generation..."
            )
            slideshow_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            slideshow_future = slideshow_executor.submit(
                generate_slideshow_pdf_from_lesson,
                lesson_data=lesson_data,
                output_pdf=slideshow_output_path,
            )

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

    if args.generate_slideshow:
        assert slideshow_output_path is not None
        try:
            if slideshow_future is not None:
                print(
                    "Finalizing slideshow PDF generation (ran in parallel with XML generation)..."
                )
                pdf_path = slideshow_future.result()
                if slideshow_executor is not None:
                    slideshow_executor.shutdown(wait=False)
            else:
                print(f"Generating slideshow PDF: {slideshow_output_path}...")
                pdf_path = generate_slideshow_pdf_from_lesson(
                    lesson_data=lesson_data,
                    output_pdf=slideshow_output_path,
                )
            print(f"✓ Generated slideshow PDF: {pdf_path}")
            if args.open_slideshow:
                try:
                    subprocess.run(
                        ["xdg-open", str(pdf_path)],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    print(f"✓ Opened slideshow: {pdf_path}")
                except Exception:
                    print(
                        f"⚠ Could not auto-open slideshow. Open it manually: {pdf_path}"
                    )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

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

    should_write_firmware = args.write_firmware or args.flash_hardware
    if should_write_firmware:
        if args.dry_run:
            print(
                "⚠ Skipping firmware write because --dry-run is enabled. "
                "Re-run without --dry-run to write firmware.",
            )
        else:
            try:
                main_path = write_lesson_firmware(
                    project_dir=args.platformio_project_dir,
                    lesson_name=lesson_name,
                    steps=steps,
                    main_rel_path=args.firmware_main_path,
                )
                print(
                    f"✓ Wrote generated firmware for {len(steps)} lesson step(s) to {main_path}",
                )
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    if args.flash_hardware:
        if args.dry_run:
            print(
                "⚠ Skipping hardware flash because --dry-run is enabled. "
                "Re-run without --dry-run to flash.",
            )
            return
        try:
            flash_hardware_with_platformio(
                project_dir=args.platformio_project_dir,
                environment=args.platformio_env,
                platformio_cmd=args.platformio_cmd,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
