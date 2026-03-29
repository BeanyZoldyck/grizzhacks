# Embettered Client

LLMs generate lesson steps as JSON → persist to MongoDB (`MONGODB_URI`).

## Files

- `lesson_cloud.py` - Builds lesson documents and inserts them into MongoDB
- `send_lesson.py` - Writes lessons (JSON steps) to MongoDB
- `ai_lesson.py` - Generate lesson with AI in one step
- `example_lesson.json` - Example lesson steps for LLMs to reference (in repo root)

## Cloud persistence (MongoDB)

Set `MONGODB_URI` and optionally `MONGODB_DATABASE`, `LESSON_PLANS_COLLECTION` in `mongo/.env`. The client uses **PyMongo** to `insert_one` into `lesson_plans` (by default).

- **`LESSON_CLOUD`** — Default `1`: insert lesson document (steps + metadata). Set to `0`, `false`, `no`, or `off` to skip.
- **`--no-cloud`** on `ai_lesson.py` / `send_lesson.py` — Same as disabling `LESSON_CLOUD` for that run.

## Usage

### Option 1: One-Step AI Generation

```bash
cd client

export ANTHROPIC_API_KEY=your_key_here

python ai_lesson.py --query "Create a 4-step lesson for wiring an LED with ESP32-C3"

python ai_lesson.py --query "Create a 3-step LED lesson" --dry-run

python ai_lesson.py --query "Create a 5-step sensor lesson" --save-json sensor_lesson.json
```

#### Advanced Options

```bash
python ai_lesson.py --query "Create a lesson..." --base-url https://api.minimax.chat/v1
python ai_lesson.py --query "Create a lesson..." --model MiniMax-M2.7
python ai_lesson.py --provider openai --query "Create a lesson..."
python ai_lesson.py --provider openai --base-url https://api.together.xyz/v1 --model llama-3.1
```

Or set in `.env`:

```bash
ANTHROPIC_API_KEY=your_key
ANTHROPIC_BASE_URL=https://api.minimax.chat/v1
ANTHROPIC_MODEL=MiniMax-M2.7

OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### Option 2: Send Pre-Generated JSON

```bash
cd client
python send_lesson.py --name "ESP32_LED_Lesson" --steps '[{"step":1,...}]'
python send_lesson.py --from-file ../example_lesson.json
python send_lesson.py --from-file ../example_lesson.json --dry-run
```

The JSON file can be either:

- A list of steps directly: `[{"step":1,...}, ...]`
- A dict with a "steps" key: `{"lesson_name":"MyLesson","steps":[{"step":1,...}, ...]}`

## Lesson step format

```json
{
  "lesson_name": "LessonName",
  "steps": [
    {
      "step": 1,
      "description": "Short description",
      "instruction": "User instruction text",
      "visuals": [
        {
          "type": "Text",
          "text": "Display text",
          "x": 500,
          "y": 100,
          "width": 200,
          "height": 50,
          "font_size": 20
        }
      ]
    }
  ]
}
```

### Visual types

- `Text` — Text overlay
- `Graphics` — Shapes (`filename`, e.g. `Rectangle.svg`)
- `Line` — Lines

### Visual properties

- `x`, `y` — Position (0–1024)
- `width`, `height` — Size
- `color` — RGB string (e.g. `"0,255,0"`)
- `font_size` — Text size
- `filename` — For `Graphics`

## Workflow

1. LLM generates lesson steps (JSON)
2. `send_lesson.py` / `ai_lesson.py` insert a document into MongoDB

## Voice from phone (same LAN)

The FastAPI host in `../fastapi/` can transcribe audio (OpenAI Whisper), run the same pipeline as `ai_lesson.py`, and persist lessons to MongoDB.

```bash
cd fastapi
pip install -r requirements.txt
python test_server.py
```

Endpoints: `POST /voice`, `POST /lesson/text`. Response includes `ws_response` (MongoDB persist result; name kept for compatibility).

## Environment

See `mongo/.env` for `MONGODB_URI`, `MONGODB_DATABASE`, and AI keys as in the sections above.

## Quick Start

```bash
export ANTHROPIC_API_KEY=your_key
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson"
```

```bash
export OPENAI_API_KEY=your_key
python ai_lesson.py --provider openai --query "Create a 4-step ESP32 LED assembly lesson"
```
