"""Main entry point for slideshow generation"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from lesson_parser import LessonParser
from pdf_generator import PDFGenerator

sys.path.insert(0, str(Path(__file__).parent.parent / "client"))


def generate_lesson_with_ai(
    query: str,
    provider: str = "anthropic",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    try:
        from ai_lesson import generate_lesson

        return generate_lesson(
            query,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
    except ImportError as e:
        print(f"Error importing ai_lesson: {e}", file=sys.stderr)
        print("Make sure the client module is available", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate PDF slideshow from lesson query or existing JSON file",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--query",
        "-q",
        help="Generate lesson from AI query (e.g., 'Create a 3-step lesson for wiring an LED with ESP32')",
    )
    input_group.add_argument(
        "--input-file",
        "-i",
        help="Load lesson from existing JSON file",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="slideshow.pdf",
        help="Output PDF filename (default: slideshow.pdf)",
    )

    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["openai", "anthropic"],
        help="AI provider for query mode (default: anthropic)",
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
        help="Model name (OPENAI_MODEL or ANTHROPIC_MODEL env var)",
    )

    parser.add_argument(
        "--save-json",
        help="Save generated lesson JSON to file (for query mode)",
    )

    args = parser.parse_args()

    try:
        lesson_data = None

        if args.query:
            print(f"Generating lesson with {args.provider}...")
            print(f"Query: {args.query[:60]}{'...' if len(args.query) > 60 else ''}")

            lesson_data = generate_lesson_with_ai(
                args.query,
                provider=args.provider,
                api_key=args.api_key,
                base_url=args.base_url,
                model=args.model,
            )

            print(
                f"✓ Generated lesson: {lesson_data.get('lesson_name', 'Generated_Lesson')}"
            )
            print(f"✓ {len(lesson_data.get('steps', []))} steps")

            if args.save_json:
                with open(args.save_json, "w") as f:
                    json.dump(lesson_data, f, indent=2)
                print(f"✓ Saved JSON to {args.save_json}")

        elif args.input_file:
            print(f"Loading lesson from {args.input_file}...")
            lesson_data = json.loads(Path(args.input_file).read_text())
            print(f"✓ Loaded lesson: {lesson_data.get('lesson_name', 'Unknown')}")
            print(f"✓ {len(lesson_data.get('steps', []))} steps")

        if not lesson_data:
            print("Error: No lesson data available", file=sys.stderr)
            sys.exit(1)

        lesson_parser = LessonParser(lesson_data=lesson_data)

        if not lesson_parser.validate():
            print("Error: Invalid lesson data structure", file=sys.stderr)
            sys.exit(1)

        print(f"Generating PDF slideshow: {args.output}...")
        pdf_generator = PDFGenerator(args.output, lesson_parser)
        pdf_generator.generate()

        print(f"✓ Successfully generated slideshow: {args.output}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
