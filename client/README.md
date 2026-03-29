# Embettered Client

Generate lessons with AI and persist JSON steps to MongoDB.

## Quick Start

```bash
cd client
export ANTHROPIC_API_KEY=your_key_here

python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson"

python ai_lesson.py --provider openai --query "Create a 4-step ESP32 LED assembly lesson"

python ai_lesson.py --query "Create a lesson..." --base-url https://api.minimax.chat/v1
python ai_lesson.py --query "Create a lesson..." --model MiniMax-M2.7
```

## Files

- `ai_lesson.py` - Generate lesson with AI in one step
- `send_lesson.py` - Persist pre-generated lesson JSON to MongoDB
- `lesson_cloud.py` - MongoDB document builder and insert

## Documentation

See [CLIENT_README.md](CLIENT_README.md) for full usage details.
