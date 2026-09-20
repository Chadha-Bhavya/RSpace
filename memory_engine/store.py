from __future__ import annotations

import json
import os
import re
import tempfile
import threading
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
                cursor.execute("ALTER TABLE memory_events ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE account_profiles ENABLE ROW LEVEL SECURITY")
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
