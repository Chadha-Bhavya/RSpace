# RSpace

## Voice demo

This FastAPI starter records a browser microphone clip, sends it to Deepgram for
speech-to-text, gets a caring reply from the isolated AI-companion layer, and
reads that reply through ElevenLabs.

Each successful transcript also passes through a privacy-filtered, evidence-grounded
memory pipeline. It redacts common PII, flags explicit safety language,
extracts supported facts with OpenAI structured parsing, validates negation and
confidence, removes recent duplicates, and stores approved events in PostgreSQL
when `DATABASE_URL` is configured, or local JSONL during development.
The original unredacted transcript is not written to the memory files. The
redacted transcript is sent to the configured OpenAI memory model with `store: false`.

1. Create a virtual environment and install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`, then add your API and Supabase settings.
3. Run `uvicorn main:app --reload`
4. Open http://127.0.0.1:8000 and allow microphone access.

The API keys stay on the server. `POST /api/transcribe` accepts a multipart
`audio` file and returns `{"transcript": "..."}`. `POST /api/speak` accepts
`{"text": "..."}` and returns MP3 audio.

`POST /api/companion` accepts `{"text": "..."}` and
returns `{"reply": "..."}`. Before generating the reply, it loads a compact
profile and up to five relevant memories. The response rules use respectful
adult language, avoid elderspeak, follow the user's topic, and ask at most one
question. If memory retrieval fails, conversation continues without memory.

The OpenAI provider lives entirely in `companion.py`, behind the
`ReplyProvider` interface. The current message and compact private context are
sent with `store: false`. Deepgram and ElevenLabs remain independent.

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

Reports contain observational social-wellness signals and supporting data only.
They explicitly do not diagnose or rule out any medical or mental-health condition.

## Authentication

RSpace uses Supabase email and password authentication. Passwords are handled
and hashed by Supabase and are never stored in the RSpace tables. FastAPI keeps
the access and refresh tokens in HTTP-only cookies. Every voice and memory route
uses the authenticated Supabase user ID, so separate accounts receive separate
memory profiles.

Add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to local and Vercel environment
variables. If Supabase email confirmation is enabled, new users must confirm by
email before logging in. For a quick hackathon demo, it can be disabled under
Supabase Authentication settings.

The app creates `account_profiles`, `memory_events`, and `user_profiles` and
enables Row Level Security on all three. The browser cannot choose another
user's ID. Private memory routes are now:

- `POST /api/memory/process` with `{"text":"I enjoy gardening"}`
- `GET /api/memory/profile`
- `GET /api/memory/search?q=plants&limit=5`
- `GET /api/memory/report`

Run local tests with `python3 -m unittest discover -s tests -v`.

## Matching

Matching is enabled for every account and disclosed during signup. A separate
matching profile contains only positive interest labels, communication
preferences, display name, and recent account activity. Raw transcripts,
evidence quotes, relationships, medical details, availability, and social
wellness signals are excluded.

Cold-start recommendations require at least two meaningful shared interests and
a score of 72% or higher. They combine semantic similarity with reciprocal
ranking rather than fixed category weights. Accept, pass, block, and disconnect
decisions train a small per-user online ranking model after five decisions.
Email addresses are returned only after both people accept the same match.

Supabase tables for profiles, impressions, decisions, connections, blocks, and
ranking models are created automatically. The matching routes are:

- `GET /api/matches`
- `POST /api/matches/{match_id}/decision` with `accept`, `pass`, or `block`
- `GET /api/connections`
- `POST /api/connections/{match_id}/disconnect`
