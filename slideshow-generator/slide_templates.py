"""Slide templates for PDF generation"""

from typing import Any
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter


class SlideTemplates:
    PAGE_WIDTH = letter[0]
    PAGE_HEIGHT = letter[1]
    MARGIN = 0.5 * inch

    COLOR_PRIMARY = HexColor("#2C3E50")
    COLOR_SECONDARY = HexColor("#3498DB")
    COLOR_ACCENT = HexColor("#E74C3C")
    COLOR_TEXT = HexColor("#2C3E50")
    COLOR_LIGHT_BG = HexColor("#ECF0F1")
    COLOR_WHITE = HexColor("#FFFFFF")

    @staticmethod
    def get_title_slide_coords() -> dict[str, float]:
        return {
            "title_y": 7.5 * inch,
            "title_height": 1.0 * inch,
            "subtitle_y": 6.5 * inch,
            "subtitle_height": 0.5 * inch,
            "logo_width": 2.0 * inch,
            "logo_height": 2.0 * inch,
        }

    @staticmethod
    def get_step_slide_coords() -> dict[str, float]:
        return {
            "header_height": 1.0 * inch,
            "content_top": 7.0 * inch,
            "instruction_height": 2.5 * inch,
            "visual_height": 3.5 * inch,
            "step_indicator_y": 0.5 * inch,
        }

    @staticmethod
    def get_summary_slide_coords() -> dict[str, float]:
        return {
            "title_y": 8.0 * inch,
            "title_height": 0.8 * inch,
            "content_start": 6.5 * inch,
            "line_height": 0.3 * inch,
        }

    @staticmethod
    def parse_color(color_str: str) -> tuple[int, int, int]:
        if isinstance(color_str, tuple):
            if len(color_str) == 3:
                return (int(color_str[0]), int(color_str[1]), int(color_str[2]))
            return (0, 0, 0)
        try:
            rgb_values = [int(x.strip()) for x in str(color_str).split(",")]
            if len(rgb_values) == 3:
                return (rgb_values[0], rgb_values[1], rgb_values[2])
            raise ValueError(f"Invalid RGB color format: {color_str}")
        except (AttributeError, ValueError, TypeError) as e:
            return (0, 0, 0)
        try:
            rgb_values = [int(x.strip()) for x in str(color_str).split(",")]
            if len(rgb_values) == 3:
                return tuple(rgb_values)
            raise ValueError(f"Invalid RGB color format: {color_str}")
        except (AttributeError, ValueError, TypeError) as e:
            return (0, 0, 0)

    @staticmethod
    def scale_coordinates(
        x: float,
        y: float,
        width: float,
        height: float,
        max_x: int = 1024,
        max_y: int = 1024,
    ) -> tuple[float, float, float, float]:
        scale_x = (SlideTemplates.PAGE_WIDTH - 2 * SlideTemplates.MARGIN) / max_x
        scale_y = (SlideTemplates.PAGE_HEIGHT - 2 * SlideTemplates.MARGIN) / max_y

        scaled_x = SlideTemplates.MARGIN + x * scale_x
        scaled_y = SlideTemplates.PAGE_HEIGHT - (SlideTemplates.MARGIN + y * scale_y)
        scaled_width = width * scale_x
        scaled_height = height * scale_y

        return (scaled_x, scaled_y, scaled_width, scaled_height)

    @staticmethod
    def get_step_visual_data(visual: dict[str, Any]) -> dict[str, Any]:
        visual_type = visual.get("type", "")

        if visual_type in ("Text", "VDFText"):
            return {
                "type": "text",
                "text": visual.get("text", ""),
                "font_size": visual.get("font_size", 20),
                "color": SlideTemplates.parse_color(visual.get("color", "0,0,0")),
                "x": visual.get("x", 500),
                "y": visual.get("y", 100),
                "width": visual.get("width", 400),
                "height": visual.get("height", 50),
            }
        elif visual_type in ("Graphics", "VDFGraphics"):
            return {
                "type": "shape",
                "filename": visual.get("filename", ""),
                "color": SlideTemplates.parse_color(visual.get("color", "0,0,0")),
                "x": visual.get("x", 400),
                "y": visual.get("y", 200),
                "width": visual.get("width", 300),
                "height": visual.get("height", 200),
            }
        elif visual_type == "Line":
            return {
                "type": "line",
                "color": SlideTemplates.parse_color(visual.get("color", "0,0,0")),
                "x": visual.get("x", 500),
                "y": visual.get("y", 350),
                "width": visual.get("width", 100),
                "height": visual.get("height", 0),
            }
        else:
            return {"type": "unknown"}
