"""FastAPI voice companion with Supabase authentication and private memory."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from auth import AuthError, create_auth_client
from companion import create_reply_provider, detect_end_conversation, retrieve_companion_context
from memory_engine import MemoryEngine
from memory_engine.filters import filter_text
from matching import create_matching_engine
from realtime import SentenceChunker

load_dotenv()

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_STREAM_URL = "wss://api.deepgram.com/v1/listen"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_TTS_STREAM_URL = "wss://api.elevenlabs.io/v1/text-to-speech"
STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(os.getenv("RSPACE_DATA_DIR", Path(__file__).parent / "data"))
ACCESS_COOKIE = "rspace_access_token"
REFRESH_COOKIE = "rspace_refresh_token"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(45.0))
    app.state.memory = MemoryEngine(DATA_DIR)
    app.state.matching = create_matching_engine(app.state.memory, DATA_DIR)
    yield
    await app.state.http.aclose()


app = FastAPI(title="RSpace Voice API", version="0.2.0", lifespan=lifespan)
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
    text: str = Field(min_length=1, max_length=10_000)


class SignUpRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)


class MatchDecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(accept|pass|block)$")


def require_setting(name: str) -> str:
    value = os.getenv(name)
    if not value or value.startswith("your_"):
        raise HTTPException(status_code=503, detail=f"{name} is not configured. Add it to your .env file.")
    return value


def upstream_error(service: str, response: httpx.Response) -> HTTPException:
    return HTTPException(status_code=502, detail=f"{service} could not complete the request (status {response.status_code}).")


def request_is_secure(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return forwarded == "https" or request.url.scheme == "https"


def set_session_cookies(response: Response, session: dict, secure: bool) -> None:
    if session.get("access_token"):
        response.set_cookie(
            ACCESS_COOKIE,
            session["access_token"],
            max_age=int(session.get("expires_in", 3600)),
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
    if session.get("refresh_token"):
        response.set_cookie(
            REFRESH_COOKIE,
            session["refresh_token"],
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def public_user(user: dict, account: dict | None = None) -> dict[str, str]:
    metadata = user.get("user_metadata") or {}
    account = account or {}
    return {
        "id": str(user.get("id", "")),
        "email": str(user.get("email") or account.get("email", "")),
        "name": str(account.get("display_name") or metadata.get("display_name") or "User"),
    }


async def require_user(request: Request) -> dict:
    access_token = request.cookies.get(ACCESS_COOKIE)
    if not access_token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    try:
        return await create_auth_client(request.app.state.http).get_user(access_token)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Authentication is temporarily unavailable.") from error


async def require_websocket_user(websocket: WebSocket) -> dict | None:
    access_token = websocket.cookies.get(ACCESS_COOKIE)
    if not access_token:
        await websocket.close(code=4401, reason="Please log in to continue.")
        return None
    try:
        return await create_auth_client(websocket.app.state.http).get_user(access_token)
    except (AuthError, RuntimeError, httpx.RequestError):
        await websocket.close(code=4401, reason="Your session is unavailable.")
        return None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/signup")
async def sign_up(credentials: SignUpRequest, request: Request) -> Response:
    display_name = " ".join(credentials.name.strip().split())
    if len(display_name) < 2:
        raise HTTPException(status_code=422, detail="Please enter your name.")
    try:
        session = await create_auth_client(request.app.state.http).sign_up(
            credentials.email.strip().lower(),
            credentials.password,
            display_name,
        )
        user = session.get("user") or {}
        if user.get("id"):
            await asyncio.to_thread(
                request.app.state.memory.store.save_account_profile,
                str(user["id"]),
                str(user.get("email") or credentials.email),
                display_name,
            )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Account creation is temporarily unavailable.") from error

    if not session.get("access_token"):
        return JSONResponse({
            "status": "confirmation_required",
            "message": "Check your email to confirm the account, then log in.",
        })

    account = {"display_name": display_name, "email": credentials.email}
    response = JSONResponse({"status": "authenticated", "user": public_user(user, account)})
    set_session_cookies(response, session, request_is_secure(request))
    return response


@app.post("/api/auth/login")
async def log_in(credentials: LoginRequest, request: Request) -> Response:
    try:
        session = await create_auth_client(request.app.state.http).sign_in(
            credentials.email.strip().lower(),
            credentials.password,
        )
        user = session.get("user") or {}
        account = await asyncio.to_thread(request.app.state.memory.store.load_account_profile, str(user["id"]))
        if not account:
            display_name = str((user.get("user_metadata") or {}).get("display_name") or "User")
            await asyncio.to_thread(
                request.app.state.memory.store.save_account_profile,
                str(user["id"]),
                str(user.get("email") or credentials.email),
                display_name,
            )
            account = {"display_name": display_name, "email": credentials.email}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Login is temporarily unavailable.") from error

    response = JSONResponse({"status": "authenticated", "user": public_user(user, account)})
    set_session_cookies(response, session, request_is_secure(request))
    return response


@app.post("/api/auth/refresh")
async def refresh_session(request: Request) -> Response:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    try:
        session = await create_auth_client(request.app.state.http).refresh(refresh_token)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail="Session refresh is temporarily unavailable.") from error
    response = JSONResponse({"status": "refreshed"})
    set_session_cookies(response, session, request_is_secure(request))
    return response


@app.get("/api/auth/me")
async def current_account(request: Request, user: dict = Depends(require_user)) -> dict[str, object]:
    account = await asyncio.to_thread(request.app.state.memory.store.load_account_profile, str(user["id"]))
    if account:
        await asyncio.to_thread(
            request.app.state.memory.store.save_account_profile,
            str(user["id"]),
            str(account.get("email") or user.get("email") or ""),
            str(account.get("display_name") or "User"),
        )
    return {"user": public_user(user, account)}


@app.post("/api/auth/logout")
async def log_out(request: Request) -> Response:
    access_token = request.cookies.get(ACCESS_COOKIE)
    if access_token:
        try:
            await create_auth_client(request.app.state.http).sign_out(access_token)
        except (AuthError, RuntimeError, httpx.RequestError):
            pass
    response = JSONResponse({"status": "logged_out"})
    clear_session_cookies(response)
    return response


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    user: dict = Depends(require_user),
) -> dict[str, object]:
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
        headers={"Authorization": f"Token {api_key}", "Content-Type": audio_type},
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
    memory = await asyncio.to_thread(app.state.memory.process, str(user["id"]), transcript) if transcript else None
    if transcript:
        await asyncio.to_thread(app.state.matching.refresh_profiles)
    return {"transcript": transcript, "memory": memory}


@app.websocket("/ws/transcribe")
async def transcribe_stream(websocket: WebSocket) -> None:
    """Relay microphone chunks to Deepgram and return one finalized utterance."""
    user = await require_websocket_user(websocket)
    if not user:
        return
    await websocket.accept()
    try:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key or api_key.startswith("your_"):
            await websocket.send_json({"type": "error", "message": "Deepgram is not configured."})
            return
        params = urlencode({
            "model": "nova-3",
            "language": "en-US",
            "smart_format": "true",
            "punctuate": "true",
            "interim_results": "true",
            "vad_events": "true",
            "endpointing": "500",
            "utterance_end_ms": "1200",
        })
        transcript_parts: list[str] = []
        browser_finished = asyncio.Event()

        async with websockets.connect(
            f"{DEEPGRAM_STREAM_URL}?{params}",
            extra_headers={"Authorization": f"Token {api_key}"},
            max_size=None,
            ping_interval=20,
        ) as deepgram:
            async def forward_audio() -> None:
                try:
                    while True:
                        message = await websocket.receive()
                        if message["type"] == "websocket.disconnect":
                            browser_finished.set()
                            await deepgram.send(json.dumps({"type": "CloseStream"}))
                            return
                        if message.get("bytes"):
                            await deepgram.send(message["bytes"])
                        elif message.get("text"):
                            command = json.loads(message["text"])
                            if command.get("type") == "finish":
                                browser_finished.set()
                                await deepgram.send(json.dumps({"type": "CloseStream"}))
                                return
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    browser_finished.set()

            forward_task = asyncio.create_task(forward_audio())
            utterance_complete = False
            try:
                async for raw_message in deepgram:
                    data = json.loads(raw_message)
                    if data.get("type") == "Results":
                        alternative = (data.get("channel", {}).get("alternatives") or [{}])[0]
                        text = str(alternative.get("transcript") or "").strip()
                        if data.get("is_final") and text:
                            transcript_parts.append(text)
                        if text:
                            await websocket.send_json({"type": "interim", "transcript": text})
                    elif data.get("type") == "UtteranceEnd" and transcript_parts:
                        utterance_complete = True
                        break
            finally:
                if not forward_task.done():
                    forward_task.cancel()
                await asyncio.gather(forward_task, return_exceptions=True)

            transcript = " ".join(transcript_parts).strip()
            await websocket.send_json({"type": "transcript", "transcript": transcript})
            if utterance_complete and not browser_finished.is_set():
                try:
                    await deepgram.send(json.dumps({"type": "CloseStream"}))
                except websockets.ConnectionClosed:
                    pass
    except Exception:
        try:
            await websocket.send_json({"type": "error", "message": "Live transcription was interrupted."})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/speak")
async def speak(request: SpeakRequest, user: dict = Depends(require_user)) -> Response:
    api_key = require_setting("ELEVENLABS_API_KEY")
    voice_id = require_setting("ELEVENLABS_VOICE_ID")
    response = await app.state.http.post(
        f"{ELEVENLABS_TTS_URL}/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Accept": "audio/mpeg"},
        json={
            "text": request.text.strip(),
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {"stability": 0.68, "similarity_boost": 0.7, "use_speaker_boost": True},
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
async def companion(request: CompanionRequest, user: dict = Depends(require_user)) -> dict[str, object]:
    try:
        user_text = request.text.strip()
        if detect_end_conversation(user_text):
            return {"reply": "Of course. Goodbye for now.", "end_conversation": True}
        filtered = filter_text(user_text)
        context = await asyncio.to_thread(
            retrieve_companion_context,
            app.state.memory,
            str(user["id"]),
            user_text,
            filtered.safety_flags,
        )
        reply = await create_reply_provider(app.state.http).reply(user_text, context)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except httpx.HTTPStatusError as error:
        raise upstream_error("The companion", error.response) from error
    except (httpx.RequestError, ValueError):
        raise HTTPException(status_code=502, detail="The companion could not prepare a reply. Please try again.")
    return {"reply": reply, "end_conversation": False}


async def persist_conversation_memory(user_id: str, text: str) -> None:
    try:
        await asyncio.to_thread(app.state.memory.process, user_id, text)
        await asyncio.to_thread(app.state.matching.refresh_profiles)
    except Exception:
        pass


@app.websocket("/ws/respond")
async def respond_stream(websocket: WebSocket) -> None:
    """Stream model text and ElevenLabs audio back over one connection."""
    user = await require_websocket_user(websocket)
    if not user:
        return
    await websocket.accept()
    memory_task: asyncio.Task | None = None
    try:
        request = await websocket.receive_json()
        user_text = str(request.get("text") or "").strip()
        if not user_text or len(user_text) > 2_000:
            await websocket.send_json({"type": "error", "message": "Please send a short message."})
            return

        ending = detect_end_conversation(user_text)
        if ending:
            async def reply_deltas():
                yield "Of course. Goodbye for now."
        else:
            filtered = filter_text(user_text)
            context = await asyncio.to_thread(
                retrieve_companion_context,
                app.state.memory,
                str(user["id"]),
                user_text,
                filtered.safety_flags,
            )
            provider = create_reply_provider(app.state.http)
            reply_deltas = lambda: provider.stream_reply(user_text, context)
            memory_task = asyncio.create_task(persist_conversation_memory(str(user["id"]), user_text))

        api_key = os.getenv("ELEVENLABS_API_KEY")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        if not api_key or not voice_id or api_key.startswith("your_") or voice_id.startswith("your_"):
            raise RuntimeError("ElevenLabs is not configured.")

        stream_params = urlencode({
            "model_id": "eleven_flash_v2_5",
            "output_format": "mp3_44100_128",
            "auto_mode": "true",
        })
        reply_parts: list[str] = []
        chunker = SentenceChunker()
        send_lock = asyncio.Lock()

        async def emit(payload: dict) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        async with websockets.connect(
            f"{ELEVENLABS_TTS_STREAM_URL}/{voice_id}/stream-input?{stream_params}",
            max_size=None,
            ping_interval=20,
        ) as elevenlabs:
            await elevenlabs.send(json.dumps({
                "text": " ",
                "xi_api_key": api_key,
                "voice_settings": {
                    "stability": 0.68,
                    "similarity_boost": 0.7,
                    "use_speaker_boost": True,
                },
            }))

            async def relay_audio() -> None:
                async for raw_message in elevenlabs:
                    data = json.loads(raw_message)
                    if data.get("audio"):
                        await emit({"type": "audio", "audio": data["audio"]})
                    if data.get("is_final"):
                        return

            audio_task = asyncio.create_task(relay_audio())
            async for delta in reply_deltas():
                reply_parts.append(delta)
                await emit({"type": "text_delta", "delta": delta})
                for sentence in chunker.push(delta):
                    await elevenlabs.send(json.dumps({"text": sentence + " "}))

            final_chunk = chunker.finish()
            if final_chunk:
                await elevenlabs.send(json.dumps({"text": final_chunk + " ", "flush": True}))
            else:
                await elevenlabs.send(json.dumps({"text": " ", "flush": True}))
            await elevenlabs.send(json.dumps({"text": ""}))
            try:
                await asyncio.wait_for(audio_task, timeout=15)
            except asyncio.TimeoutError:
                audio_task.cancel()
                await asyncio.gather(audio_task, return_exceptions=True)

        await emit({
            "type": "response_done",
            "reply": "".join(reply_parts).strip(),
            "end_conversation": ending,
        })
        if memory_task:
            await memory_task
    except Exception:
        try:
            await websocket.send_json({"type": "error", "message": "Realtime reply was interrupted."})
        except Exception:
            pass
    finally:
        if memory_task and not memory_task.done():
            memory_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/memory/process")
async def process_memory(request: MemoryRequest, user: dict = Depends(require_user)) -> dict[str, object]:
    try:
        result = await asyncio.to_thread(app.state.memory.process, str(user["id"]), request.text)
        await asyncio.to_thread(app.state.matching.refresh_profiles)
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/profile")
async def memory_profile(user: dict = Depends(require_user)) -> dict[str, object]:
    try:
        return await asyncio.to_thread(app.state.memory.profile, str(user["id"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/search")
async def search_memory(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
    user: dict = Depends(require_user),
) -> list[dict]:
    try:
        return await asyncio.to_thread(app.state.memory.search, str(user["id"]), q, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/memory/report")
async def memory_report(user: dict = Depends(require_user)) -> dict[str, object]:
    try:
        return await asyncio.to_thread(app.state.memory.report, str(user["id"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/matches")
async def list_matches(user: dict = Depends(require_user)) -> list[dict[str, object]]:
    try:
        return await asyncio.to_thread(app.state.matching.find_matches, str(user["id"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/matches/{match_id}/decision")
async def decide_match(
    match_id: str,
    choice: MatchDecisionRequest,
    user: dict = Depends(require_user),
) -> dict[str, object]:
    try:
        return await asyncio.to_thread(app.state.matching.decide, str(user["id"]), match_id, choice.decision)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/connections")
async def list_connections(user: dict = Depends(require_user)) -> list[dict[str, object]]:
    return await asyncio.to_thread(app.state.matching.connections, str(user["id"]))


@app.post("/api/connections/{match_id}/disconnect")
async def disconnect_match(match_id: str, user: dict = Depends(require_user)) -> dict[str, str]:
    try:
        await asyncio.to_thread(app.state.matching.disconnect, str(user["id"]), match_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"status": "disconnected"}


@app.get("/")
async def demo() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
