# Product Requirements Document (PRD)

## Embettered — Embedded systems learning platform

**Version:** 1.0  
**Date:** March 28, 2026  
**Project:** GrizzHacks Hackathon Entry  

**Repository note (current codebase):** LightGuide / AR projection and the LightGuidePy SDK are **not** part of this repo. Lessons are generated as JSON (with optional `Text` / `Graphics` / `Line` visuals) and persisted to **MongoDB**; **FastAPI** handles voice/text lesson generation and **ESP32** code handles LAN pings.

---

## 1. Overview

Embettered is an embedded-systems learning flow: AI-generated **lesson steps** (JSON), storage in MongoDB, a **host FastAPI** service for voice and text prompts, and an **ESP32** client for connectivity demos. Downstream consumers read lesson documents from the database (direct PyMongo inserts from the client and FastAPI).

---

## 2. Problem Statement

Learning embedded systems is intimidating for beginners. Challenges include:

- **Wiring confusion:** Datasheets and 2D diagrams are hard to translate to physical circuits.
- **Context switching:** Learners constantly shift between a screen tutorial and the physical workspace, losing focus and making mistakes.
- **Lack of real-time feedback:** Static guides cannot adapt to the learner's pace or confirm correct placement.
- **High barrier to entry:** The gap between "I bought a microcontroller kit" and "I built something that works" is too wide.

---

## 3. Goals & Success Criteria

| Goal | Metric |
|---|---|
| Reduce wiring errors for first-time embedded learners | ≥50% fewer incorrect connections vs. paper/video tutorials |
| Enable a complete beginner to assemble an ESP32-C3 circuit | User can complete a guided build in < 30 minutes |
| Real-time, spatially-accurate projection of assembly steps | Projections align within ±5 mm of physical component footprints |
| End-to-end connectivity between host and LightGuide | < 500 ms latency from step trigger to projection update |

---

## 4. System Architecture

### 4.1 Component Overview

The system consists of two primary subsystems connected via a MongoDB-backed WebSocket bridge:

```
┌─────────────────────────┐         WebSocket / MongoDB         ┌─────────────────────────┐
│      HOST COMPUTER      │ ◄──────────────────────────────────► │   LIGHTGUIDE AR SYSTEM  │
│                         │                                      │                         │
│  • Lesson engine        │         ws://host:8765               │  • LightGuide projector │
│  • Visualization gen    │         (JSON payloads)              │  • LightGuidePy SDK     │
│  • FastAPI server       │                                      │  • Projection surface   │
│  • MongoDB client       │                                      │                         │
│  • ESP32 comm (Wi-Fi)   │                                      │                         │
└─────────────────────────┘                                      └─────────────────────────┘
         ▲
         │  HTTP POST /ping
         │  (JSON over Wi-Fi)
         ▼
┌─────────────────────────┐
│    ESP32-C3 DEV BOARD   │
│                         │
│  • Arduino firmware     │
│  • Wi-Fi connectivity   │
│  • Periodic heartbeat   │
└─────────────────────────┘
```

### 4.2 Subsystem Details

#### A. Host Computer (this repository — `src/`, `fastapi/`, `mongo/`)

| Layer | Technology | Purpose |
|---|---|---|
| **ESP32 Firmware** | PlatformIO + Arduino (ESP-IDF) | Runs on the ESP32-C3; connects to Wi-Fi and sends periodic JSON heartbeats to the host |
| **FastAPI Server** | Python, FastAPI, Uvicorn | Accepts `/ping` POSTs from the ESP32, validates device identity, and acts as the HTTP ingress |
| **MongoDB WebSocket Bridge** | Python, `websockets`, `pymongo` | Bi-directional WebSocket client that relays visualization commands to/from a MongoDB-backed gateway |

#### B. LightGuide AR System (`LightGuidePy-main/`)

| Layer | Technology | Purpose |
|---|---|---|
| **LightGuide Hardware** | LightGuide projector unit | Projects light-based AR overlays (lines, shapes, text) onto the physical work surface |
| **LightGuidePy SDK** | Python, `requests` | Full Python SDK wrapping the LightGuide REST API — controls execution flow, variables, programs, window management, and user auth |

---

## 5. Functional Requirements

### FR-1: Guided Assembly Lessons

| ID | Requirement |
|---|---|
| FR-1.1 | The system SHALL present assembly instructions as a sequence of discrete steps. |
| FR-1.2 | Each step SHALL include at minimum: a projected component outline, connection lines between pins, and a text label describing the action. |
| FR-1.3 | The user SHALL be able to advance to the next step, go back to the previous step, or restart the lesson via the LightGuide execution controls (`/Execution/Next`, `/Execution/Back`, `/Execution/Restart`). |
| FR-1.4 | The system SHALL support multiple lesson programs selectable via the LightGuide Programs API (`/Programs/Run`, `/Programs`). |

### FR-2: Visual Projections

| ID | Requirement |
|---|---|
| FR-2.1 | The LightGuide system SHALL project outlines (rectangles, component footprints) indicating where to place physical parts. |
| FR-2.2 | The system SHALL project lines indicating wiring paths between component pins. |
| FR-2.3 | The system SHALL project text labels for component names, pin identifiers, and instructional notes. |
| FR-2.4 | Projections SHALL update within 500 ms of a step change command. |

### FR-3: ESP32-C3 Device Communication

| ID | Requirement |
|---|---|
| FR-3.1 | The ESP32-C3 firmware SHALL connect to a configured Wi-Fi network on boot. |
| FR-3.2 | The device SHALL send a JSON heartbeat (`{"msg":"hello","device":"esp32c3","id":"<MAC>"}`) to the FastAPI server at a configurable interval (default: 10 s). |
| FR-3.3 | The FastAPI server SHALL acknowledge each ping with `{"status":"ok"}`. |
| FR-3.4 | The host SHALL use the heartbeat to confirm the learner's ESP32 is powered on and network-connected before starting a lesson. |

### FR-4: MongoDB WebSocket Bridge

| ID | Requirement |
|---|---|
| FR-4.1 | The host computer SHALL connect to a WebSocket gateway backed by MongoDB. |
| FR-4.2 | The bridge SHALL support sending JSON-encoded visualization payloads to the LightGuide system. |
| FR-4.3 | The bridge SHALL support receiving status/acknowledgement messages from the LightGuide system. |
| FR-4.4 | The client SHALL optionally ping MongoDB on startup to verify database connectivity. |

### FR-5: LightGuide SDK Integration

| ID | Requirement |
|---|---|
| FR-5.1 | The system SHALL use `LightGuideClient` to programmatically control lesson execution (run, next, back, abort, restart). |
| FR-5.2 | The system SHALL use LightGuide variables to track lesson state (e.g., current step, completion flags). |
| FR-5.3 | The system SHALL display status messages and errors via the LightGuide HMI (`/Application/Message`, `/Application/Error`). |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Latency:** End-to-end step transition (host → WebSocket → LightGuide projection) SHALL complete in < 500 ms on a local network. |
| NFR-2 | **Reliability:** The ESP32 firmware SHALL automatically reconnect to Wi-Fi if the connection drops (20 s timeout). |
| NFR-3 | **Portability:** The host software SHALL run on Linux, macOS, and Windows (Python 3.12+). |
| NFR-4 | **Security:** Wi-Fi credentials and MongoDB URIs SHALL be stored in environment variables or `.env` files, never hard-coded in production. |
| NFR-5 | **Ease of Setup:** A new user SHALL be able to set up the full system (flash ESP32, run host server, connect LightGuide) in < 15 minutes with documentation. |

---

## 7. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-1 | Beginner learner | See projected outlines on my desk showing where to place my ESP32 and breadboard | I don't have to guess component placement from a 2D diagram |
| US-2 | Beginner learner | See projected wiring lines from ESP32 pin X to breadboard row Y | I can wire connections correctly without cross-referencing a schematic |
| US-3 | Beginner learner | Advance through steps at my own pace | I'm not overwhelmed and can verify each connection before moving on |
| US-4 | Beginner learner | See my ESP32 detected as "online" before the lesson starts | I know my board is powered and connected before I begin wiring |
| US-5 | Lesson author | Define a new assembly program with step sequences | I can create custom lessons for different circuits and skill levels |
| US-6 | System operator | Verify MongoDB and LightGuide connectivity from the CLI | I can troubleshoot setup issues quickly |

---

## 8. Tech Stack Summary

| Component | Technology |
|---|---|
| Microcontroller | ESP32-C3 (esp32-c3-devkitm-1) |
| Firmware framework | Arduino via PlatformIO |
| Host HTTP server | FastAPI + Uvicorn (Python) |
| Real-time messaging | WebSocket (`websockets` library) |
| Database / state store | MongoDB Atlas or local (`pymongo`) |
| AR projection | LightGuide System (lightguidesys.com) |
| AR SDK | LightGuidePy (`requests`-based REST client) |
| Environment management | `python-dotenv`, `.env` files |
| Build tooling | PlatformIO (firmware), `uv` / `pip` (Python) |

---

## 9. Data Flow

```
1. User powers on ESP32-C3
2. ESP32 connects to Wi-Fi, begins sending heartbeat pings to FastAPI server
3. Host detects device online via /ping endpoint
4. User selects a lesson program on the host
5. Host sends visualization payload (step 1 geometry + text) via WebSocket → MongoDB gateway
6. LightGuide system receives payload, projects visual guides onto work surface
7. User places component, presses "Next"
8. LightGuide SDK triggers /Execution/Next, host sends next step's visualization
9. Repeat steps 6-8 until lesson complete
10. Host sends completion message → LightGuide displays "Lesson Complete!" on surface
```

---

## 10. Current State & Roadmap

### Implemented (MVP / Hackathon)

- [x] ESP32-C3 firmware: Wi-Fi connect + JSON heartbeat ping
- [x] FastAPI test server: `/ping` endpoint with JSON acknowledgement
- [x] MongoDB WebSocket client: connect, send/receive JSON, ping MongoDB
- [x] LightGuidePy SDK: full REST API coverage (execution control, variables, programs, users, database, window management)

### Next Steps

#### CLient side 

- [ ] convert lesson step into xml files with a one shot
- [ ] send xml through mongo websocket 
- [ ] vibe the software for the esp32
- [ ] flash the hardware at the end

#### Server side 

- [ ] receive xml files form the client
- [ ] write the files to the right locations (viz in viz and tools in tools )
- [ ] refresh the program with the sdk 
- [ ] go through each step till the user reaches the end

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LightGuide projection misalignment | Users place components incorrectly | Calibration routine at lesson start; ±5 mm tolerance |
| Wi-Fi latency / drops on hackathon network | Steps lag or ESP32 appears offline | Reconnect logic in firmware; local network fallback |
| MongoDB gateway not yet built | No end-to-end data flow | Can test with direct WebSocket server stub |
| LightGuide hardware availability | Cannot demo AR projection | Develop with simulated LightGuide (mock REST API) |

---

## 12. Glossary

| Term | Definition |
|---|---|
| **LightGuide** | An AR projection system by LightGuide Systems that projects visual instructions onto physical surfaces |
| **LightGuidePy** | Python SDK for the LightGuide REST API |
| **ESP32-C3** | RISC-V based Wi-Fi microcontroller by Espressif |
| **PlatformIO** | Cross-platform build system for embedded development |
| **HMI** | Human-Machine Interface — the LightGuide operator display |
| **WebSocket Gateway** | Server that bridges WebSocket connections to MongoDB operations |
