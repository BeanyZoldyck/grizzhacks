# Slideshow Generator

Generate PDF slideshows from Embettered lesson data, either via AI query or from existing JSON files.

## Installation

```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.12+
- ReportLab (PDF generation)
- Anthropic or OpenAI API key (for AI query mode)

## Usage

### Run from project root (recommended)

```bash
client/.venv/bin/python run_slideshow.py --input-file example_lesson.json --output tutorial.pdf
```

### Generate slideshow from AI query

```bash
client/.venv/bin/python run_slideshow.py --query "Create a 3-step lesson for wiring an LED with ESP32" --output led_tutorial.pdf
```

### Generate slideshow from existing JSON file

```bash
client/.venv/bin/python run_slideshow.py --input-file example_lesson.json --output tutorial.pdf
```

### Advanced options

```bash
client/.venv/bin/python run_slideshow.py \
  --query "ESP32 sensor integration tutorial" \
  --output sensor_tutorial.pdf \
  --provider openai \
  --model gpt-4 \
  --save-json generated_lesson.json
```

## Features

- **AI-powered lesson generation**: Create lessons from natural language queries
- **PDF slideshow output**: Professional PDF presentations
- **Step-by-step formatting**: Each lesson step gets its own slide
- **Visual elements**: Supports text, shapes, and wiring diagrams
- **Title and summary slides**: Complete slideshow structure
- **Color-coordinated design**: Professional styling with consistent colors

## Output Format

Generated PDFs include:

1. **Title Slide**: Lesson name, description, and step count
2. **Step Slides**: One slide per lesson step with:
   - Step number and description
   - Detailed instruction text
   - Visual representations (text, shapes, wiring)
3. **Summary Slide**: Complete lesson overview

## Integration

This module integrates with the existing `client/ai_lesson.py` system to:
- Use the same lesson JSON schema
- Share AI generation functions
- Maintain consistency with the Embettered platform (`client/ai_lesson.py` lesson JSON schema)

## Examples

### Basic LED tutorial

```bash
client/.venv/bin/python run_slideshow.py \
  --query "Create a step-by-step tutorial for wiring an LED to ESP32-C3" \
  --output led_basic.pdf
```

### Complex sensor integration

```bash
client/.venv/bin/python run_slideshow.py \
  --query "Create a comprehensive lesson for connecting DHT22 temperature sensor to ESP32" \
  --output sensor_integration.pdf \
  --provider anthropic
```

### From existing lesson data

```bash
client/.venv/bin/python run_slideshow.py \
  --input-file example_lesson.json \
  --output advanced_circuit.pdf
```

## Configuration

Set environment variables for API keys:

```bash
# For Anthropic (default)
export ANTHROPIC_API_KEY="your-api-key"

# For OpenAI
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1/chat/completions"
```

## File Structure

```
slideshow-generator/
├── __init__.py              # Module initialization
├── __main__.py              # Module entry point
├── generate_slideshow.py    # Main CLI interface
├── pdf_generator.py         # PDF generation logic
├── lesson_parser.py         # Lesson JSON parsing
├── slide_templates.py       # Slide layout templates
├── requirements.txt         # Python dependencies
└── README.md               # This file

run_slideshow.py             # Convenience script from project root
simple_test.py               # Simple test script
```

## Development

### Adding new visual types

Extend `slide_templates.py` to support new visual element types from the lesson schema.

### Customizing slide layouts

Modify `pdf_generator.py` to change slide styling, colors, or layout.

### New lesson formats

Update `lesson_parser.py` to support additional lesson data formats.