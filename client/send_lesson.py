"""Persist lesson steps (JSON) to MongoDB.

Usage:
    python send_lesson.py --name "MyLesson" --steps '[{"step":1,...}]'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mongo"))

from lesson_cloud import send_lesson_to_mongodb
from websocket_client import load_env

load_env()


async def send_lesson(
    lesson_name: str,
    steps: list[dict],
    *,
    enable_cloud: bool | None = None,
    description: str | None = None,
    source: str | None = None,
) -> None:
    """Write lesson to MongoDB (see LESSON_CLOUD)."""
    try:
        await send_lesson_to_mongodb(
            lesson_name,
            steps,
            description=description,
            source=source or "send_lesson",
            enable_cloud=enable_cloud,
            verbose=True,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persist lesson to MongoDB (MONGODB_URI)",
    )
    parser.add_argument(
        "--name",
        help="Lesson name (e.g., ESP32_LED_Lesson). Can also be specified in JSON file as 'lesson_name'",
    )
    parser.add_argument(
        "--steps",
        help="Lesson steps as JSON string (e.g., '[{\"step\":1,...}]')",
    )
    parser.add_argument(
        "--from-file",
        help="Read steps from JSON file instead of --steps",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print lesson JSON but don't write to MongoDB",
    )
    parser.add_argument(
        "--no-cloud",
        action="store_true",
        help="Skip MongoDB insert",
    )

    args = parser.parse_args()

    if not args.steps and not args.from_file:
        print("Error: --steps or --from-file is required", file=sys.stderr)
        sys.exit(1)

    description: str | None = None
    try:
        if args.from_file:
            with open(args.from_file) as f:
                data = json.load(f)
            if isinstance(data, dict) and "steps" in data:
                steps = data["steps"]
                lesson_name = data.get("lesson_name") or args.name
                description = data.get("description")
            else:
                steps = data
                lesson_name = args.name
        else:
            steps = json.loads(args.steps)
            lesson_name = args.name
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(1)

    if not lesson_name:
        print(
            "Error: --name is required or include 'lesson_name' in JSON file",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run:
        payload = {"lesson_name": lesson_name, "steps": steps}
        if description is not None:
            payload["description"] = description
        print("--- Dry run ---")
        print(json.dumps(payload, indent=2))
    else:
        enable_cloud = False if args.no_cloud else None
        asyncio.run(
            send_lesson(
                lesson_name,
                steps,
                enable_cloud=enable_cloud,
                description=description,
            )
        )


if __name__ == "__main__":
    main()
