"""Coordinate transforms between tool layer and viz layer.

Derived from matched regions in:
- HelloWorld_topleft.xml <-> tool_optical_topleft.xml
- HelloWorld.xml <-> tool_detect_optical.xml
"""

from __future__ import annotations

from typing import Tuple


# Linear mapping coefficients:
# viz_x = SCALE_X * tool_x + OFFSET_X
# viz_y = SCALE_Y * tool_y + OFFSET_Y
SCALE_X = 1.9256637168141593
OFFSET_X = 18.04778761061947
SCALE_Y = 1.9
OFFSET_Y = -53.0


def tool_to_viz(x_tool: float, y_tool: float) -> Tuple[float, float]:
    """Convert a point from tool coordinates to viz coordinates."""
    x_viz = SCALE_X * x_tool + OFFSET_X
    y_viz = SCALE_Y * y_tool + OFFSET_Y
    return x_viz, y_viz


def viz_to_tool(x_viz: float, y_viz: float) -> Tuple[float, float]:
    """Convert a point from viz coordinates to tool coordinates."""
    x_tool = (x_viz - OFFSET_X) / SCALE_X
    y_tool = (y_viz - OFFSET_Y) / SCALE_Y
    return x_tool, y_tool


if __name__ == "__main__":
    # Example: known point from tool_detect_optical.xml
    tool_point = (606, 195)
    viz_point = tool_to_viz(*tool_point)
    print(f"tool -> viz: {tool_point} -> {viz_point}")

    # Round-trip check
    print(f"viz -> tool: {viz_point} -> {viz_to_tool(*viz_point)}")
