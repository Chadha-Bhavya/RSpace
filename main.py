"""A small FastAPI voice layer for RSpace.

The browser records a short audio clip, Deepgram turns it into text, and
ElevenLabs turns a supplied reply into friendly spoken audio.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from companion import create_reply_provider

load_dotenv()

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(45.0))
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
async def transcribe(audio: UploadFile = File(...)) -> dict[str, str]:
    """Transcribe a browser-recorded audio file with Deepgram."""
    api_key = require_setting("DEEPGRAM_API_KEY")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Please record a short message first.")
    if len(audio_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Please keep the recording under 15 MB.")

    response = await app.state.http.post(
        DEEPGRAM_LISTEN_URL,
        params={"model": "nova-3", "smart_format": "true", "punctuate": "true"},
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": audio.content_type or "audio/webm",
        },
        content=audio_bytes,
    )
    if response.is_error:
        raise upstream_error("Deepgram", response)

    data = response.json()
    transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "").strip()
    return {"transcript": transcript}


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


@app.get("/")
async def demo() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
