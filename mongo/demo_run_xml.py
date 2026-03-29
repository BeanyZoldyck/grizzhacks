"""Demo CLI: run a local XML lesson on a LightGuide machine.

This script copies an XML file into the LightGuide program root (optional) and
starts it through the LightGuide SDK.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


def _sdk_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "LightGuidePy-main" / "LightGuidePy"


import sys

sys.path.insert(0, str(_sdk_path()))
from lightguide_client import LightGuideClient  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an XML program on LightGuide using LightGuidePy",
    )
    parser.add_argument(
        "xml_file",
        help="Path to local XML file to run",
    )
    parser.add_argument(
        "--lightguide-url",
        default=os.environ.get("LIGHTGUIDE_BASE_URL", "http://127.0.0.1:54274"),
        help="LightGuide base URL",
    )
    parser.add_argument(
        "--program-root",
        default=os.environ.get("LIGHTGUIDE_PROGRAM_ROOT"),
        help=(
            "If set, copy XML to this folder before running. If omitted, xml_file "
            "must already be accessible by LightGuide at the provided path."
        ),
    )
    parser.add_argument(
        "--subdir",
        default="viz",
        help="Subdirectory under --program-root to place XML (default: viz)",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for program completion when calling /Programs/Run",
    )
    return parser


def _copy_to_program_root(xml_path: Path, program_root: Path, subdir: str) -> str:
    target_dir = program_root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / xml_path.name
    shutil.copy2(xml_path, target_file)
    return f"{subdir.strip('/')}/{xml_path.name}"


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    args = build_parser().parse_args()

    xml_path = Path(args.xml_file).expanduser().resolve()
    if not xml_path.exists() or not xml_path.is_file():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    if xml_path.suffix.lower() != ".xml":
        raise ValueError(f"Expected an .xml file, got: {xml_path.name}")

    client = LightGuideClient(base_url=args.lightguide_url)

    if args.program_root:
        program_root = Path(args.program_root).expanduser().resolve()
        program_path = _copy_to_program_root(xml_path, program_root, args.subdir)
    else:
        program_path = str(xml_path)

    try:
        client.run_mode()
    except Exception:
        pass

    client.run_program(program_path, wait=args.wait)
    client.message(f"Demo started: {program_path}")
    print(f"Started LightGuide program: {program_path}")


if __name__ == "__main__":
    main()
