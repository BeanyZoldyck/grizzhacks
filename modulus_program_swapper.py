"""Hot-swap LightGuide XML programs using StepTimeMain modulus buckets.

This controller treats each scene as a separate XML program and swaps programs
when the StepTimeMain bucket changes.
"""

from __future__ import annotations

import argparse
import time

from lightguide_client import LightGuideClient


def _parse_step_time_main(payload: object) -> float:
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


def run_swap_loop(
    *,
    base_url: str,
    cycle_seconds: float,
    poll_seconds: float,
    scene_programs: list[str],
) -> None:
    if cycle_seconds <= 0:
        raise ValueError("cycle_seconds must be > 0")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")
    if not scene_programs:
        raise ValueError("At least one scene program is required")

    client = LightGuideClient(base_url=base_url)
    scene_count = len(scene_programs)

    client.abort()
    client.run_mode()

    current_idx: int | None = None
    while True:
        response = client.get_variable("StepTimeMain")
        step_time_main = _parse_step_time_main(response)
        target_idx = _bucket_index(step_time_main, cycle_seconds, scene_count)

        if target_idx != current_idx:
            program = scene_programs[target_idx]
            client.run_program(program, wait=False)
            client.message(
                f"Scene {target_idx + 1}/{scene_count}: {program} (t={step_time_main:.2f}s)"
            )
            current_idx = target_idx

        time.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Swap XML programs based on StepTimeMain modulus",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:54274",
        help="LightGuide API base URL",
    )
    parser.add_argument(
        "--cycle-seconds",
        type=float,
        default=10.0,
        help="Total seconds across all scenes before repeating",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=0.2,
        help="Polling interval for StepTimeMain",
    )
    parser.add_argument(
        "--scene",
        action="append",
        dest="scenes",
        help=(
            "Scene XML program path as seen by LightGuide. Repeat --scene for each "
            "scene. Default uses scenes/Scene1.xml..scenes/Scene4.xml"
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scene_programs = args.scenes or [
        "scenes/Scene1.xml",
        "scenes/Scene2.xml",
        "scenes/Scene3.xml",
        "scenes/Scene4.xml",
    ]

    try:
        run_swap_loop(
            base_url=args.base_url,
            cycle_seconds=args.cycle_seconds,
            poll_seconds=args.poll_seconds,
            scene_programs=scene_programs,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
