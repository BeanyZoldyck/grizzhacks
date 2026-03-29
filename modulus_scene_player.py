"""Drive LightGuide XML scenes using StepTimeMain modulus buckets.

Example with 4 scenes and 10-second cycle:
- phase = StepTimeMain % 10.0
- bucket = 10.0 / 4 = 2.5 seconds
- scene index is selected by phase bucket:
  [0.0, 2.5) -> scene 1
  [2.5, 5.0) -> scene 2
  [5.0, 7.5) -> scene 3
  [7.5, 10.0) -> scene 4
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


def _move_to_scene(client: LightGuideClient, current_idx: int | None, target_idx: int) -> int:
    if current_idx is None:
        current_idx = 0

    if target_idx < current_idx:
        client.restart()
        current_idx = 0

    while current_idx < target_idx:
        client.next()
        current_idx += 1

    return current_idx


def run_modulus_scene_loop(
    *,
    base_url: str,
    program_path: str,
    cycle_seconds: float,
    scene_count: int,
    poll_seconds: float,
    write_scene_variable: bool,
) -> None:
    if cycle_seconds <= 0:
        raise ValueError("cycle_seconds must be > 0")
    if scene_count <= 0:
        raise ValueError("scene_count must be > 0")

    client = LightGuideClient(base_url=base_url)

    client.abort()
    client.run_mode()
    client.run_program(program_path, wait=False)
    client.message(
        f"Modulus scene loop started: cycle={cycle_seconds:.2f}s scenes={scene_count}"
    )

    time.sleep(max(poll_seconds, 0.15))

    current_idx: int | None = 0
    while True:
        response = client.get_variable("StepTimeMain")
        step_time_main = _parse_step_time_main(response)
        target_idx = _bucket_index(step_time_main, cycle_seconds, scene_count)

        if target_idx != current_idx:
            current_idx = _move_to_scene(client, current_idx, target_idx)
            if write_scene_variable:
                try:
                    client.set_variable("CurrentSceneIndex", current_idx + 1)
                except Exception:
                    pass

        time.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Display XML scenes by StepTimeMain modulus buckets",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:54274",
        help="LightGuide API base URL",
    )
    parser.add_argument(
        "--program",
        default="HelloWorld_ModulusScenes.xml",
        help="Program path sent to /Programs/Run",
    )
    parser.add_argument(
        "--cycle-seconds",
        type=float,
        default=10.0,
        help="Total time for one full scene cycle",
    )
    parser.add_argument(
        "--scene-count",
        type=int,
        default=4,
        help="Number of scene buckets",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=0.1,
        help="Polling interval for StepTimeMain",
    )
    parser.add_argument(
        "--write-scene-variable",
        action="store_true",
        help="Write CurrentSceneIndex variable (only if this variable exists)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        run_modulus_scene_loop(
            base_url=args.base_url,
            program_path=args.program,
            cycle_seconds=args.cycle_seconds,
            scene_count=args.scene_count,
            poll_seconds=args.poll_seconds,
            write_scene_variable=args.write_scene_variable,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
