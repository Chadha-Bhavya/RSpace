# RSpace

## Voice demo

This FastAPI starter records a browser microphone clip, sends it to Deepgram for
speech-to-text, gets a caring reply from the isolated AI-companion layer, and
reads that reply through ElevenLabs.

1. Create a virtual environment and install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`, then add your Deepgram and ElevenLabs API keys.
3. Run `uvicorn main:app --reload`
4. Open http://127.0.0.1:8000 and allow microphone access.

The API keys stay on the server. `POST /api/transcribe` accepts a multipart
`audio` file and returns `{"transcript": "..."}`. `POST /api/speak` accepts
`{"text": "..."}` and returns MP3 audio.

`POST /api/companion` accepts `{"text": "..."}` and returns `{"reply": "..."}`.
The temporary OpenAI provider lives entirely in `companion.py`, behind the
`ReplyProvider` interface. Replace `create_reply_provider` with the team’s
future reply service without changing browser, Deepgram, or ElevenLabs code.
