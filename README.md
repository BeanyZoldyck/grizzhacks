# Pinpoint

Embedded lesson generation and ESP32 / FastAPI demo.

Files of interest:
- `platformio.ini` - PlatformIO project file (environment `esp32-c3`).
- `src/config.h` - Edit this file with your Wi‑Fi SSID/password and `SERVER_ENDPOINT` (e.g. `http://192.168.1.42:8000/ping`).
- `src/main.cpp` - ESP32 code (sends a JSON payload every `PING_INTERVAL_MS`).
- `fastapi/test_server.py` - FastAPI server that accepts `/ping` POSTs and replies with an acknowledgement.
- `fastapi/requirements.txt` - Python requirements for the test server.

Usage

1) Configure the ESP32 project
   - Edit `src/config.h` and set `WIFI_SSID`, `WIFI_PASS`, and `SERVER_ENDPOINT`.

2) Build and flash to your connected ESP32-C3
   - Install PlatformIO (VSCode PlatformIO extension or `pip install platformio`).
   - Run: `platformio run -e esp32-c3 -t upload` (or use the IDE).

3) Run the FastAPI test server on your PC
   - From the `fastapi` directory create a venv and install requirements:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python test_server.py
```

4) Point the device at the server
   - Set `SERVER_ENDPOINT` to `http://<your-pc-ip>:8000/ping` and flash the device.
   - When the device successfully pings the server you'll see the JSON printed in the FastAPI server logs and the ESP serial monitor will show response status.

Notes
- This is minimal example code for testing. For production use consider TLS, retries, exponential backoff, and OTA updates.
