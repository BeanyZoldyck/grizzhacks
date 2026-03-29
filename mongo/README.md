## LightGuide lesson runner

`lightguide_runner.py` implements the server-side PRD flow for running XML lessons on
the LightGuide machine.

What it does:

- Connects to the WebSocket gateway (`MONGODB_WS_URI` or `--ws-uri`)
- Receives XML payloads from the client
- Writes XML files into local `viz/` and `tools/` folders under a program root
- Uses `LightGuideClient` from `LightGuidePy-main/LightGuidePy/` to run and control
  the program (`run`, `next`, `back`, `restart`, `abort`)
- Syncs lesson state to LightGuide variables (`LessonCurrentStep`,
  `LessonComplete`, `LessonProgram`)
- Sends status/error acknowledgements back over WebSocket

### Run

```bash
python lightguide_runner.py --ws-uri ws://127.0.0.1:8765 --lightguide-url http://127.0.0.1:54274
```

Optional flags:

- `--ping-mongo` (with optional `--mongo-uri`) to verify DB connectivity on startup
- `--program-root` to choose where incoming XML files are written

### Expected WebSocket messages

Upload/start lesson:

```json
{
  "type": "lesson_xml",
  "program": "viz/main.xml",
  "step_count": 8,
  "viz": {
    "main.xml": "<LightGuideProgram>...</LightGuideProgram>",
    "step1.xml": "..."
  },
  "tools": {
    "shared.xml": "..."
  }
}
```

Advance/back/restart/abort:

```json
{
  "type": "lesson_control",
  "action": "next"
}
```

Runner responses:

- `{"type":"lightguide_status", ...}`
- `{"type":"lightguide_error", ...}`

## Demo: run one XML file

Use `demo_run_xml.py` to quickly run a single XML on the LightGuide machine.

```bash
python demo_run_xml.py /path/to/lesson.xml --lightguide-url http://127.0.0.1:54274 --program-root /path/to/lightguide/programs
```

Notes:

- With `--program-root`, the XML is copied into `<program-root>/viz/` and then run
  by relative path (for example, `viz/lesson.xml`).
- Without `--program-root`, the script passes the XML path directly to
  `/Programs/Run`.
