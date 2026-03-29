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

# Optional: flash connected ESP32 via PlatformIO after lesson processing
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson" --flash-hardware

# Write generated firmware only (no flash)
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson" --write-firmware

# Generate slideshow PDF from the same lesson data
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson" --generate-slideshow

# Generate and open slideshow after XML stage finishes
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson" --generate-slideshow --save-tool-xml-dir client/xml --open-slideshow

# One-command happy path: slideshow + firmware + flash
python ai_lesson.py --query "Create a 4-step ESP32 LED assembly lesson" --generate-slideshow --flash-hardware
```

## Files

- `ai_lesson.py` - Generate lesson with AI in one step
- `send_lesson.py` - Persist pre-generated lesson JSON to MongoDB
- `lesson_cloud.py` - MongoDB document builder and insert

## Documentation

See [CLIENT_README.md](CLIENT_README.md) for full usage details.
