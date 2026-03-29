"""Parse lesson JSON data for slideshow generation"""

import json
from typing import Any
from pathlib import Path


class LessonParser:
    def __init__(
        self, lesson_data: dict[str, Any] | None = None, json_path: str | None = None
    ):
        if lesson_data:
            self.data = lesson_data
        elif json_path:
            self.data = self._load_json(json_path)
        else:
            raise ValueError("Either lesson_data or json_path must be provided")

    def _load_json(self, json_path: str) -> dict[str, Any]:
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Lesson JSON file not found: {json_path}")

        with open(path, "r") as f:
            return json.load(f)

    @property
    def lesson_name(self) -> str:
        return self.data.get("lesson_name", "Untitled Lesson")

    @property
    def description(self) -> str:
        return self.data.get("description", "")

    @property
    def steps(self) -> list[dict[str, Any]]:
        return self.data.get("steps", [])

    def get_step_count(self) -> int:
        return len(self.steps)

    def get_step(self, step_num: int) -> dict[str, Any]:
        for step in self.steps:
            if step.get("step") == step_num:
                return step
        raise ValueError(f"Step {step_num} not found in lesson")

    def validate(self) -> bool:
        if not self.lesson_name:
            return False
        if not self.steps:
            return False
        for step in self.steps:
            if "step" not in step:
                return False
            if "description" not in step:
                return False
            if "instruction" not in step:
                return False
        return True
