from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .models import MemoryEvent


class MemoryStore(Protocol):
    @staticmethod
    def safe_user_id(user_id: str) -> str: ...

    def load_events(self, user_id: str) -> list[MemoryEvent]: ...

    def append_events(self, user_id: str, events: list[MemoryEvent]) -> None: ...

    def save_profile(self, user_id: str, profile: dict[str, Any]) -> None: ...

    def load_profile(self, user_id: str) -> dict[str, Any]: ...

    def save_account_profile(self, user_id: str, email: str, display_name: str) -> None: ...

    def load_account_profile(self, user_id: str) -> dict[str, Any]: ...

    def list_account_profiles(self) -> list[dict[str, Any]]: ...

    def start_conversation(self, user_id: str, timezone_name: str) -> dict[str, Any]: ...

    def conversation_context(self, user_id: str, session_id: str) -> dict[str, Any]: ...

    def save_conversation_turns(
        self, user_id: str, session_id: str, turns: list[dict[str, str]]
    ) -> None: ...

    def touch_conversation(self, user_id: str, session_id: str) -> None: ...

    def end_conversation(self, user_id: str, session_id: str) -> None: ...


def safe_user_id(user_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip())[:80]
    if not safe:
        raise ValueError("A valid user ID is required.")
    return safe


class JsonlMemoryStore:
    """Simple local text storage suitable for the hackathon prototype."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @staticmethod
    def safe_user_id(user_id: str) -> str:
        return safe_user_id(user_id)

    def _user_dir(self, user_id: str) -> Path:
        path = self.root / self.safe_user_id(user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def load_events(self, user_id: str) -> list[MemoryEvent]:
        path = self._user_dir(user_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[MemoryEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    events.append(MemoryEvent.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
        return events

    def append_events(self, user_id: str, events: list[MemoryEvent]) -> None:
        if not events:
            return
        path = self._user_dir(user_id) / "events.jsonl"
        with self._lock, path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")

    def save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        directory = self._user_dir(user_id)
        destination = directory / "profile.json"
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(prefix="profile-", suffix=".json", dir=directory)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(profile, handle, ensure_ascii=False, indent=2)
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)

    def load_profile(self, user_id: str) -> dict[str, Any]:
        path = self._user_dir(user_id) / "profile.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_account_profile(self, user_id: str, email: str, display_name: str) -> None:
        directory = self._user_dir(user_id)
        destination = directory / "account.json"
        payload = {"user_id": user_id, "email": email, "display_name": display_name}
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(prefix="account-", suffix=".json", dir=directory)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)

    def load_account_profile(self, user_id: str) -> dict[str, Any]:
        path = self._user_dir(user_id) / "account.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def list_account_profiles(self) -> list[dict[str, Any]]:
        accounts: list[dict[str, Any]] = []
        for path in self.root.glob("*/account.json"):
            try:
                account = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if account.get("user_id"):
                accounts.append(account)
        return accounts

    def _sessions_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / "conversation_sessions.json"

    def _load_sessions(self, user_id: str) -> list[dict[str, Any]]:
        path = self._sessions_path(user_id)
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return value if isinstance(value, list) else []

    def _save_sessions(self, user_id: str, sessions: list[dict[str, Any]]) -> None:
        directory = self._user_dir(user_id)
        destination = self._sessions_path(user_id)
        descriptor, temporary_name = tempfile.mkstemp(prefix="sessions-", suffix=".json", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(sessions, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def start_conversation(self, user_id: str, timezone_name: str) -> dict[str, Any]:
        user_id = self.safe_user_id(user_id)
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "session_id": uuid.uuid4().hex,
            "user_id": user_id,
            "started_at": now,
            "ended_at": None,
            "last_turn_at": None,
            "turn_count": 0,
            "timezone": timezone_name,
            "turns": [],
        }
        with self._lock:
            sessions = self._load_sessions(user_id)
            sessions.append(session)
            self._save_sessions(user_id, sessions[-100:])
        return self.conversation_context(user_id, session["session_id"])

    def conversation_context(self, user_id: str, session_id: str) -> dict[str, Any]:
        user_id = self.safe_user_id(user_id)
        sessions = self._load_sessions(user_id)
        current = next((item for item in sessions if item.get("session_id") == session_id), None)
        if not current:
            return {}
        earlier = [
            item for item in sessions
            if item.get("session_id") != session_id and item.get("started_at") < current.get("started_at", "")
        ]
        previous = max(earlier, key=lambda item: item.get("started_at", ""), default=None)
        recent_turns: list[dict[str, str]] = []
        for session in sessions:
            for turn in session.get("turns", []):
                if turn.get("role") in {"user", "assistant"} and turn.get("content"):
                    recent_turns.append({
                        "role": str(turn["role"]),
                        "content": str(turn["content"]),
                        "created_at": str(turn.get("created_at") or ""),
                    })
        recent_turns.sort(key=lambda item: item["created_at"])
        return {
            "current_session": current,
            "previous_session": previous,
            "recent_turns": recent_turns[-6:],
        }

    def save_conversation_turns(
        self, user_id: str, session_id: str, turns: list[dict[str, str]]
    ) -> None:
        user_id = self.safe_user_id(user_id)
        now = datetime.now(timezone.utc).isoformat()
        cleaned = [
            {
                "role": str(turn.get("role") or ""),
                "content": str(turn.get("content") or "").strip()[:2_000],
                "created_at": now,
            }
            for turn in turns
            if turn.get("role") in {"user", "assistant"} and str(turn.get("content") or "").strip()
        ]
        if not cleaned:
            return
        with self._lock:
            sessions = self._load_sessions(user_id)
            for session in sessions:
                if session.get("session_id") == session_id:
                    session["turns"] = (list(session.get("turns") or []) + cleaned)[-20:]
                    session["turn_count"] = int(session.get("turn_count") or 0) + 1
                    session["last_turn_at"] = now
                    break
            self._save_sessions(user_id, sessions)

    def touch_conversation(self, user_id: str, session_id: str) -> None:
        user_id = self.safe_user_id(user_id)
        with self._lock:
            sessions = self._load_sessions(user_id)
            for session in sessions:
                if session.get("session_id") == session_id:
                    session["turn_count"] = int(session.get("turn_count") or 0) + 1
                    session["last_turn_at"] = datetime.now(timezone.utc).isoformat()
                    break
            self._save_sessions(user_id, sessions)

    def end_conversation(self, user_id: str, session_id: str) -> None:
        user_id = self.safe_user_id(user_id)
        with self._lock:
            sessions = self._load_sessions(user_id)
            for session in sessions:
                if session.get("session_id") == session_id and not session.get("ended_at"):
                    session["ended_at"] = datetime.now(timezone.utc).isoformat()
                    break
            self._save_sessions(user_id, sessions)


class PostgresMemoryStore:
    """Persistent Supabase/PostgreSQL storage for serverless deployments."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required for PostgreSQL storage.")
        self.database_url = database_url
        self._initialized = False
        self._schema_lock = threading.Lock()

    @staticmethod
    def safe_user_id(user_id: str) -> str:
        return safe_user_id(user_id)

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("Install psycopg[binary] to use DATABASE_URL.") from error
        # Supabase's transaction pooler does not support prepared statements.
        return psycopg.connect(self.database_url, prepare_threshold=None)

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(format(float(value), ".10g") for value in values) + "]"

    @staticmethod
    def _parse_vector(value: Any) -> list[float]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        text = str(value).strip().strip("[]")
        return [float(item) for item in text.split(",") if item]

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._schema_lock:
            if self._initialized:
                return
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_events (
                        event_id text PRIMARY KEY,
                        user_id text NOT NULL,
                        created_at timestamptz NOT NULL,
                        kind text NOT NULL,
                        value text NOT NULL,
                        confidence double precision NOT NULL,
                        evidence text NOT NULL,
                        attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
                        embedding extensions.vector(384),
                        embedding_backend text NOT NULL DEFAULT ''
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS memory_events_user_created_idx "
                    "ON memory_events (user_id, created_at DESC)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id text PRIMARY KEY,
                        profile jsonb NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS account_profiles (
                        user_id text PRIMARY KEY,
                        email text NOT NULL,
                        display_name text NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_sessions (
                        session_id text PRIMARY KEY,
                        user_id text NOT NULL,
                        started_at timestamptz NOT NULL,
                        ended_at timestamptz,
                        last_turn_at timestamptz,
                        turn_count integer NOT NULL DEFAULT 0,
                        timezone text NOT NULL DEFAULT 'UTC'
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        turn_id text PRIMARY KEY,
                        session_id text NOT NULL,
                        user_id text NOT NULL,
                        role text NOT NULL CHECK (role IN ('user', 'assistant')),
                        content text NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS conversation_sessions_user_started_idx "
                    "ON conversation_sessions (user_id, started_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS conversation_turns_user_created_idx "
                    "ON conversation_turns (user_id, created_at DESC)"
                )
                cursor.execute("ALTER TABLE memory_events ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE account_profiles ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY")
            self._initialized = True

    def load_events(self, user_id: str) -> list[MemoryEvent]:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_id, user_id, created_at, kind, value, confidence,
                       evidence, attributes, embedding::text, embedding_backend
                FROM memory_events
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            MemoryEvent(
                event_id=row[0],
                user_id=row[1],
                timestamp=row[2].isoformat(),
                kind=row[3],
                value=row[4],
                confidence=float(row[5]),
                evidence=row[6],
                attributes=dict(row[7] or {}),
                embedding=self._parse_vector(row[8]),
                embedding_backend=row[9],
            )
            for row in rows
        ]

    def append_events(self, user_id: str, events: list[MemoryEvent]) -> None:
        if not events:
            return
        self._ensure_schema()
        from psycopg.types.json import Jsonb

        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            for event in events:
                cursor.execute(
                    """
                    INSERT INTO memory_events (
                        event_id, user_id, created_at, kind, value, confidence,
                        evidence, attributes, embedding, embedding_backend
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::extensions.vector, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event.event_id,
                        user_id,
                        event.timestamp,
                        event.kind,
                        event.value,
                        event.confidence,
                        event.evidence,
                        Jsonb(event.attributes),
                        self._vector_literal(event.embedding),
                        event.embedding_backend,
                    ),
                )

    def save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        self._ensure_schema()
        from psycopg.types.json import Jsonb

        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_profiles (user_id, profile, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (user_id) DO UPDATE
                SET profile = EXCLUDED.profile, updated_at = now()
                """,
                (user_id, Jsonb(profile)),
            )

    def load_profile(self, user_id: str) -> dict[str, Any]:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT profile FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
        return dict(row[0]) if row else {}

    def save_account_profile(self, user_id: str, email: str, display_name: str) -> None:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO account_profiles (user_id, email, display_name, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (user_id) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    updated_at = now()
                """,
                (user_id, email.strip().lower(), display_name.strip()),
            )

    def load_account_profile(self, user_id: str) -> dict[str, Any]:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, display_name, created_at, updated_at "
                "FROM account_profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
        if not row:
            return {}
        return {
            "user_id": row[0],
            "email": row[1],
            "display_name": row[2],
            "created_at": row[3].isoformat(),
            "updated_at": row[4].isoformat(),
        }

    def list_account_profiles(self) -> list[dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, display_name, created_at, updated_at "
                "FROM account_profiles ORDER BY created_at ASC"
            )
            rows = cursor.fetchall()
        return [
            {
                "user_id": row[0],
                "email": row[1],
                "display_name": row[2],
                "created_at": row[3].isoformat(),
                "updated_at": row[4].isoformat(),
            }
            for row in rows
        ]

    @staticmethod
    def _session_row(row: Any) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "session_id": row[0],
            "user_id": row[1],
            "started_at": row[2].isoformat(),
            "ended_at": row[3].isoformat() if row[3] else None,
            "last_turn_at": row[4].isoformat() if row[4] else None,
            "turn_count": int(row[5]),
            "timezone": row[6],
        }

    def start_conversation(self, user_id: str, timezone_name: str) -> dict[str, Any]:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        session_id = uuid.uuid4().hex
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversation_sessions "
                "(session_id, user_id, started_at, timezone) VALUES (%s, %s, now(), %s)",
                (session_id, user_id, timezone_name),
            )
        return self.conversation_context(user_id, session_id)

    def conversation_context(self, user_id: str, session_id: str) -> dict[str, Any]:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        columns = (
            "session_id, user_id, started_at, ended_at, last_turn_at, turn_count, timezone"
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {columns} FROM conversation_sessions "
                "WHERE user_id = %s AND session_id = %s",
                (user_id, session_id),
            )
            current_row = cursor.fetchone()
            if not current_row:
                return {}
            cursor.execute(
                f"SELECT {columns} FROM conversation_sessions "
                "WHERE user_id = %s AND session_id <> %s AND started_at < %s "
                "ORDER BY started_at DESC LIMIT 1",
                (user_id, session_id, current_row[2]),
            )
            previous_row = cursor.fetchone()
            cursor.execute(
                "SELECT role, content, created_at FROM conversation_turns "
                "WHERE user_id = %s ORDER BY created_at DESC LIMIT 6",
                (user_id,),
            )
            turn_rows = list(reversed(cursor.fetchall()))
        return {
            "current_session": self._session_row(current_row),
            "previous_session": self._session_row(previous_row),
            "recent_turns": [
                {"role": row[0], "content": row[1], "created_at": row[2].isoformat()}
                for row in turn_rows
            ],
        }

    def save_conversation_turns(
        self, user_id: str, session_id: str, turns: list[dict[str, str]]
    ) -> None:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        cleaned = [
            (str(turn.get("role") or ""), str(turn.get("content") or "").strip()[:2_000])
            for turn in turns
            if turn.get("role") in {"user", "assistant"} and str(turn.get("content") or "").strip()
        ]
        if not cleaned:
            return
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE conversation_sessions SET turn_count = turn_count + 1, last_turn_at = now() "
                "WHERE user_id = %s AND session_id = %s",
                (user_id, session_id),
            )
            if cursor.rowcount != 1:
                return
            for role, content in cleaned:
                cursor.execute(
                    "INSERT INTO conversation_turns (turn_id, session_id, user_id, role, content) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (uuid.uuid4().hex, session_id, user_id, role, content),
                )

    def touch_conversation(self, user_id: str, session_id: str) -> None:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE conversation_sessions SET turn_count = turn_count + 1, last_turn_at = now() "
                "WHERE user_id = %s AND session_id = %s",
                (user_id, session_id),
            )

    def end_conversation(self, user_id: str, session_id: str) -> None:
        self._ensure_schema()
        user_id = self.safe_user_id(user_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE conversation_sessions SET ended_at = COALESCE(ended_at, now()) "
                "WHERE user_id = %s AND session_id = %s",
                (user_id, session_id),
            )
