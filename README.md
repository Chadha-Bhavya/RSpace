# RSpace

## Voice demo

This FastAPI starter records a browser microphone clip, sends it to Deepgram for
speech-to-text, gets a caring reply from the isolated AI-companion layer, and
reads that reply through ElevenLabs.

Each successful transcript also passes through a fully local, explainable
memory pipeline. It redacts common PII, flags explicit safety language,
extracts supported facts with deterministic rules, validates negation and
confidence, removes recent duplicates, and stores approved events in PostgreSQL
when `DATABASE_URL` is configured, or local JSONL during development.
The original unredacted transcript is not written to the memory files.

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

## Memory engine

For a deployed app, set `DATABASE_URL` to the Supabase shared transaction-pooler
URL. The app creates `memory_events` and `user_profiles` automatically and uses
pgvector for the 384-dimensional embeddings. Without `DATABASE_URL`, memory is
written to per-user JSONL files inside the ignored `data/` directory.

The default dependency-free hashing vectors avoid external embedding APIs. For
stronger local semantic vectors:

```bash
pip install -r requirements-local-embeddings.txt
export RSPACE_EMBEDDING_BACKEND=sentence-transformers
```

The transformer model downloads once; conversation text is embedded locally.
Available endpoints:

- `POST /api/memory/process` with `{"user_id":"demo_user","text":"I enjoy gardening"}`
- `GET /api/memory/{user_id}/profile`
- `GET /api/memory/{user_id}/search?q=plants&limit=5`
- `GET /api/memory/{user_id}/report`

Reports contain observational social-wellness signals and supporting data only.
They explicitly do not diagnose or rule out any medical or mental-health condition.

Run local tests with `python3 -m unittest discover -s tests -v`.
