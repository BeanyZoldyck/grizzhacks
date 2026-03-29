"""FastAPI: ESP32 /ping, voice lesson ingest for same-LAN mobile apps."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
import uvicorn

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "client"))

load_dotenv(_ROOT / "mongo" / ".env")
load_dotenv(_ROOT / ".env", override=False)

from ai_lesson import generate_lesson, send_lesson  # noqa: E402

app = FastAPI(title="Embettered host", version="1.0.0")


class Ping(BaseModel):
    msg: str
    device: str
    id: str


class LessonTextBody(BaseModel):
    query: str = Field(..., min_length=1)
    provider: str = Field(default="openai", pattern="^(openai|anthropic)$")


def _tts_text_from_lesson(lesson_data: dict) -> str:
    steps = lesson_data.get("steps") or []
    if not steps:
        return (lesson_data.get("description") or "").strip()
    parts: list[str] = []
    for step in steps[:5]:
        text = (step.get("instruction") or step.get("description") or "").strip()
        if text:
            parts.append(text)
    return " ".join(parts) if parts else (lesson_data.get("lesson_name") or "").strip()


def _transcribe_whisper(data: bytes, filename: str | None) -> str:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="openai package not installed on server",
        ) from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set (required for Whisper)",
        )

    client = OpenAI(api_key=api_key)
    buf = io.BytesIO(data)
    buf.name = filename or "audio.m4a"
    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Whisper transcription failed: {e!s}",
        ) from e
    return transcription.text.strip()


async def _run_lesson_from_query(
    query: str,
    *,
    provider: str = "openai",
    persist_mongo: bool = True,
) -> dict:
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty transcript or query")

    try:
        lesson_data = generate_lesson(query, provider=provider)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    lesson_name = lesson_data.get("lesson_name", "Generated_Lesson")
    steps = lesson_data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HTTPException(
            status_code=502,
            detail="Lesson JSON missing 'steps' array",
        )

    tts_text = _tts_text_from_lesson(lesson_data)
    persist_response: dict | None = None
    raw_desc = lesson_data.get("description")

    if persist_mongo:
        try:
            persist_response = await send_lesson(
                lesson_name,
                steps,
                verbose=False,
                description=raw_desc if isinstance(raw_desc, str) else None,
                source="fastapi",
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"MongoDB persist failed: {e!s}",
            ) from e

    return {
        "ok": True,
        "lesson_name": lesson_name,
        "step_count": len(steps),
        "tts_text": tts_text,
        "ws_response": persist_response,
    }


@app.post("/ping")
async def receive_ping(p: Ping):
    print(f"Received ping from {p.device} id={p.id} msg={p.msg}")
    return {"status": "ok", "received": p.model_dump()}


@app.post("/voice")
async def voice_lesson(
    file: UploadFile = File(...),
    provider: str = Query("openai", description="LLM provider after transcription"),
):
    """Upload audio; transcribe with Whisper; generate lesson and persist to MongoDB."""
    if provider not in ("openai", "anthropic"):
        raise HTTPException(status_code=400, detail="provider must be openai or anthropic")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcript = _transcribe_whisper(raw, file.filename)

    result = await _run_lesson_from_query(
        transcript,
        provider=provider,
        persist_mongo=True,
    )
    result["transcript"] = transcript
    return result


@app.post("/lesson/text")
async def lesson_from_text(body: LessonTextBody):
    """Same as /voice but with a text prompt (no Whisper). Optional on-device STT path."""
    result = await _run_lesson_from_query(
        body.query.strip(),
        provider=body.provider,
        persist_mongo=True,
    )
    result["transcript"] = body.query.strip()
    return result


if __name__ == "__main__":
    uvicorn.run("test_server:app", host="0.0.0.0", port=8000, log_level="info")
