"""A small FastAPI voice layer for RSpace.

The browser records a short audio clip, Deepgram turns it into text, and
ElevenLabs turns a supplied reply into friendly spoken audio.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from companion import create_reply_provider
from memory_engine import MemoryEngine

load_dotenv()

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(os.getenv("RSPACE_DATA_DIR", Path(__file__).parent / "data"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(45.0))
    app.state.memory = MemoryEngine(DATA_DIR)
    yield
    await app.state.http.aclose()


app = FastAPI(title="RSpace Voice API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_500, examples=["Of course. I am here with you."])


class CompanionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000, examples=["I have been feeling lonely lately."])


class MemoryRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=10_000)


def require_setting(name: str) -> str:
    value = os.getenv(name)
    if not value or value.startswith("your_"):
        raise HTTPException(status_code=503, detail=f"{name} is not configured. Add it to your .env file.")
    return value


def upstream_error(service: str, response: httpx.Response) -> HTTPException:
    # Do not pass upstream bodies through: they can contain account details.
    return HTTPException(status_code=502, detail=f"{service} could not complete the request (status {response.status_code}).")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    user_id: str = Form(default="demo_user"),
) -> dict[str, object]:
    """Transcribe audio, then process the text through the local memory engine."""
    api_key = require_setting("DEEPGRAM_API_KEY")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Please record a short message first.")
    if len(audio_bytes) < 1_024:
        raise HTTPException(status_code=400, detail="The recording was too short. Please speak for a moment and try again.")
    if len(audio_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Please keep the recording under 15 MB.")

    audio_type = (audio.content_type or "audio/webm").split(";", 1)[0].strip().lower()
    if audio_type not in {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/mpeg", "audio/aiff"}:
        audio_type = "audio/webm"

    response = await app.state.http.post(
        DEEPGRAM_LISTEN_URL,
        params={"model": "nova-3", "smart_format": "true", "punctuate": "true"},
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": audio_type,
        },
        content=audio_bytes,
    )
    if response.is_error:
        if response.status_code == 400:
            raise HTTPException(
                status_code=400,
                detail="Deepgram could not read that recording. Please speak clearly for at least one second and try again.",
            )
        raise upstream_error("Deepgram", response)

    data = response.json()
    transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "").strip()
    memory = await asyncio.to_thread(app.state.memory.process, user_id, transcript) if transcript else None
    return {"transcript": transcript, "memory": memory}


@app.post("/api/speak")
async def speak(request: SpeakRequest) -> Response:
    """Turn a concise, reassuring reply into MP3 audio with ElevenLabs."""
    api_key = require_setting("ELEVENLABS_API_KEY")
    voice_id = require_setting("ELEVENLABS_VOICE_ID")
    response = await app.state.http.post(
        f"{ELEVENLABS_TTS_URL}/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Accept": "audio/mpeg"},
        json={
            "text": request.text.strip(),
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.68, "similarity_boost": 0.7, "style": 0.15, "use_speaker_boost": True},
        },
    )
    if response.is_error:
        if response.status_code == 402:
            raise HTTPException(
                status_code=502,
                detail="This ElevenLabs voice is not available through your current plan. Choose an API-enabled voice or upgrade the plan.",
            )
        raise upstream_error("ElevenLabs", response)
    return Response(content=response.content, media_type="audio/mpeg")


@app.post("/api/companion")
async def companion(request: CompanionRequest) -> dict[str, str]:
    """Generate a caring reply; this is deliberately separate from speech I/O."""
    try:
        reply = await create_reply_provider(app.state.http).reply(request.text.strip())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except httpx.HTTPStatusError as error:
        raise upstream_error("The companion", error.response) from error
    except (httpx.RequestError, ValueError):
        raise HTTPException(status_code=502, detail="The companion could not prepare a reply. Please try again.")
    return {"reply": reply}


@app.post("/api/memory/process")
async def process_memory(request: MemoryRequest) -> dict[str, object]:
    """Process text directly; useful for testing and non-voice clients."""
    try:
        return await asyncio.to_thread(app.state.memory.process, request.user_id, request.text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/{user_id}/profile")
async def memory_profile(user_id: str) -> dict[str, object]:
    try:
        return await asyncio.to_thread(app.state.memory.profile, user_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/{user_id}/search")
async def search_memory(
    user_id: str,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict]:
    try:
        return await asyncio.to_thread(app.state.memory.search, user_id, q, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/{user_id}/report")
async def memory_report(user_id: str) -> dict[str, object]:
    try:
        return await asyncio.to_thread(app.state.memory.report, user_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/")
async def demo() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
