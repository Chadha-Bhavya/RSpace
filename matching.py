from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx

from memory_engine.embeddings import Embedder, cosine_similarity

MATCH_THRESHOLD = 0.72
MIN_SHARED_INTERESTS = 1
MIN_LEARNING_DECISIONS = 5
MODEL_FEATURES = 4
ACTIVE_WINDOW = timedelta(days=90)
INTEREST_SIMILARITY_THRESHOLD = 0.62
EMBEDDING_DIMENSIONS = 384
DEMO_MATCH_TARGET_EMAIL_HASH = "a7d39dee6e0ce9f78e1ff85de04321d4a12a43e6973c02fc998d4095bde9f1d4"
DEMO_MATCH_USER_ID = "rspace-demo-friend"
DEMO_MATCH_EMAIL = "julia@rspace.app"
DEMO_MATCH_NAME = "Julia"
SENSITIVE_MATCH_PATTERN = re.compile(
    r"\b(?:lonel(?:y|iness)|depress(?:ion|ed)?|anxi(?:ety|ous)|dementia|alzheimer(?:'s)?|"
    r"suicid(?:e|al)?|self[- ]harm|cancer|diabet(?:es|ic)|diagnos\w*|disease|disorder|"
    r"syndrome|medication|medicine|hospital|doctor|therapy|therapist|grief|bereave\w*|"
    r"disabilit\w*|chronic pain|mental health|medical)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pair_id(user_a: str, user_b: str) -> str:
    first, second = sorted((user_a, user_b))
    return hashlib.sha256(f"{first}|{second}".encode()).hexdigest()[:24]


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, value))))


def _clean_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for item in values:
        value = " ".join(str(item).strip().lower().split())
        if value and not SENSITIVE_MATCH_PATTERN.search(value) and value not in cleaned:
            cleaned.append(value[:80])
    return cleaned[:30]


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.0] * EMBEDDING_DIMENSIONS
    dimensions = len(vectors[0])
    mean = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in mean)) or 1.0
    return [value / norm for value in mean]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class InterestEmbeddingProvider(Protocol):
    name: str

    def embed_many(self, values: list[str]) -> dict[str, list[float]]: ...


class LocalInterestEmbeddingProvider:
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self.name = embedder.name

    def embed_many(self, values: list[str]) -> dict[str, list[float]]:
        return {value: self.embedder.embed(value) for value in values}


class OpenAIInterestEmbeddingProvider:
    """Meaning-based interest embeddings using OpenAI's embeddings endpoint."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model = model
        self.name = f"openai:{model}:{EMBEDDING_DIMENSIONS}"

    def embed_many(self, values: list[str]) -> dict[str, list[float]]:
        if not values:
            return {}
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "input": values,
                "dimensions": EMBEDDING_DIMENSIONS,
                "encoding_format": "float",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        rows = sorted(response.json().get("data", []), key=lambda item: item.get("index", 0))
        if len(rows) != len(values):
            raise RuntimeError("The embedding service returned an incomplete response.")
        embeddings: dict[str, list[float]] = {}
        for value, row in zip(values, rows):
            vector = [float(item) for item in row["embedding"]]
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise RuntimeError("The embedding service returned an unexpected vector size.")
            embeddings[value] = _normalize_vector(vector)
        return embeddings


@dataclass
class MatchProfile:
    user_id: str
    display_name: str
    interests: list[str]
    communication_preferences: list[str]
    interest_embeddings: dict[str, list[float]]
    embedding: list[float]
    embedding_backend: str
    last_active_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "interests": self.interests,
            "communication_preferences": self.communication_preferences,
            "interest_embeddings": self.interest_embeddings,
            "embedding": self.embedding,
            "embedding_backend": self.embedding_backend,
            "last_active_at": self.last_active_at,
        }


class MatchingRepository(Protocol):
    def get_interest_embeddings(self, user_id: str, backend: str) -> dict[str, list[float]]: ...
    def save_profile(self, profile: MatchProfile) -> None: ...
    def list_profiles(self) -> list[MatchProfile]: ...
    def save_match(self, match: dict[str, Any]) -> None: ...
    def list_matches(self, user_id: str) -> list[dict[str, Any]]: ...
    def get_match(self, match_id: str) -> dict[str, Any]: ...
    def save_decision(self, match_id: str, user_id: str, decision: str) -> dict[str, Any]: ...
    def block(self, blocker_id: str, blocked_id: str) -> None: ...
    def disconnect(self, match_id: str, user_id: str) -> None: ...
    def get_model(self, user_id: str) -> dict[str, Any]: ...
    def save_model(self, user_id: str, weights: list[float], decision_count: int) -> None: ...


class JsonMatchingRepository:
    """Small persistent repository for local development and tests."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "matching.json"
        self._lock = threading.RLock()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"profiles": {}, "matches": {}, "blocks": [], "models": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data.setdefault("profiles", {})
        data.setdefault("matches", {})
        data.setdefault("blocks", [])
        data.setdefault("models", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix="matching-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def save_profile(self, profile: MatchProfile) -> None:
        with self._lock:
            data = self._load()
            data["profiles"][profile.user_id] = profile.to_dict()
            self._save(data)

    def get_interest_embeddings(self, user_id: str, backend: str) -> dict[str, list[float]]:
        with self._lock:
            profile = self._load()["profiles"].get(user_id, {})
        if profile.get("embedding_backend") != backend:
            return {}
        return {
            str(interest): [float(value) for value in vector]
            for interest, vector in profile.get("interest_embeddings", {}).items()
        }

    def list_profiles(self) -> list[MatchProfile]:
        with self._lock:
            rows = self._load()["profiles"].values()
        profiles = []
        for row in rows:
            row = dict(row)
            row.setdefault("interest_embeddings", {})
            row.setdefault("embedding_backend", "legacy")
            profiles.append(MatchProfile(**row))
        return profiles

    def save_match(self, match: dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            existing = data["matches"].get(match["match_id"], {})
            if existing:
                match["status"] = existing["status"]
                match["decisions"] = existing.get("decisions", {})
            data["matches"][match["match_id"]] = {**existing, **match}
            self._save(data)

    def list_matches(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._load()
            blocked = {tuple(item) for item in data["blocks"]}
            rows = []
            for match in data["matches"].values():
                if user_id not in {match["user_a"], match["user_b"]}:
                    continue
                other = match["user_b"] if match["user_a"] == user_id else match["user_a"]
                if (user_id, other) in blocked or (other, user_id) in blocked:
                    continue
                rows.append(dict(match))
            return rows

    def get_match(self, match_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._load()["matches"].get(match_id, {}))

    def save_decision(self, match_id: str, user_id: str, decision: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            match = data["matches"].get(match_id)
            if not match or user_id not in {match["user_a"], match["user_b"]}:
                raise ValueError("Match not found.")
            match.setdefault("decisions", {})[user_id] = decision
            other = match["user_b"] if match["user_a"] == user_id else match["user_a"]
            if decision == "block":
                match["status"] = "blocked"
                if [user_id, other] not in data["blocks"]:
                    data["blocks"].append([user_id, other])
            elif decision == "pass":
                match["status"] = "passed"
            elif match["decisions"].get(other) == "accept":
                match["status"] = "connected"
                match["connected_at"] = _now()
            else:
                match["status"] = "pending"
            match["updated_at"] = _now()
            self._save(data)
            return dict(match)

    def block(self, blocker_id: str, blocked_id: str) -> None:
        with self._lock:
            data = self._load()
            if [blocker_id, blocked_id] not in data["blocks"]:
                data["blocks"].append([blocker_id, blocked_id])
            self._save(data)

    def disconnect(self, match_id: str, user_id: str) -> None:
        with self._lock:
            data = self._load()
            match = data["matches"].get(match_id)
            if not match or user_id not in {match["user_a"], match["user_b"]}:
                raise ValueError("Connection not found.")
            match["status"] = "disconnected"
            match["disconnected_at"] = _now()
            match["updated_at"] = _now()
            self._save(data)

    def get_model(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._load()["models"].get(user_id, {}))

    def save_model(self, user_id: str, weights: list[float], decision_count: int) -> None:
        with self._lock:
            data = self._load()
            data["models"][user_id] = {"weights": weights, "decision_count": decision_count, "updated_at": _now()}
            self._save(data)


class PostgresMatchingRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._initialized = False
        self._lock = threading.Lock()

    def _connect(self):
        import psycopg
        return psycopg.connect(self.database_url, prepare_threshold=None)

    @staticmethod
    def _vector(values: list[float]) -> str:
        return "[" + ",".join(format(float(value), ".10g") for value in values) + "]"

    @staticmethod
    def _parse_vector(value: Any) -> list[float]:
        return [float(item) for item in str(value).strip().strip("[]").split(",") if item]

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            statements = [
                """CREATE TABLE IF NOT EXISTS matching_profiles (
                    user_id text PRIMARY KEY, display_name text NOT NULL, interests jsonb NOT NULL,
                    communication_preferences jsonb NOT NULL, embedding extensions.vector(384) NOT NULL,
                    embedding_backend text NOT NULL DEFAULT '', last_active_at timestamptz NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now())""",
                "ALTER TABLE matching_profiles ADD COLUMN IF NOT EXISTS embedding_backend text NOT NULL DEFAULT ''",
                """CREATE TABLE IF NOT EXISTS matching_interest_embeddings (
                    user_id text NOT NULL, interest text NOT NULL,
                    embedding extensions.vector(384) NOT NULL, embedding_backend text NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(user_id, interest))""",
                """CREATE TABLE IF NOT EXISTS match_candidates (
                    match_id text PRIMARY KEY, user_a text NOT NULL, user_b text NOT NULL,
                    score double precision NOT NULL, reasons jsonb NOT NULL, features jsonb NOT NULL,
                    status text NOT NULL DEFAULT 'pending', decisions jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
                    connected_at timestamptz, disconnected_at timestamptz, UNIQUE(user_a, user_b))""",
                """CREATE TABLE IF NOT EXISTS match_impressions (
                    match_id text NOT NULL, viewer_id text NOT NULL, candidate_id text NOT NULL,
                    features jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY(match_id, viewer_id))""",
                """CREATE TABLE IF NOT EXISTS match_decisions (
                    match_id text NOT NULL, user_id text NOT NULL, decision text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(match_id, user_id))""",
                """CREATE TABLE IF NOT EXISTS connections (
                    match_id text PRIMARY KEY, user_a text NOT NULL, user_b text NOT NULL,
                    connected_at timestamptz NOT NULL DEFAULT now(), disconnected_at timestamptz)""",
                """CREATE TABLE IF NOT EXISTS blocked_users (
                    blocker_id text NOT NULL, blocked_id text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(blocker_id, blocked_id))""",
                """CREATE TABLE IF NOT EXISTS ranking_models (
                    user_id text PRIMARY KEY, weights jsonb NOT NULL, decision_count integer NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now())""",
            ]
            with self._connect() as connection, connection.cursor() as cursor:
                from psycopg import sql
                for statement in statements:
                    cursor.execute(statement)
                for table in ("matching_profiles", "matching_interest_embeddings", "match_candidates", "match_impressions", "match_decisions", "connections", "blocked_users", "ranking_models"):
                    cursor.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(sql.Identifier(table)))
            self._initialized = True

    def get_interest_embeddings(self, user_id: str, backend: str) -> dict[str, list[float]]:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT interest, embedding::text FROM matching_interest_embeddings "
                "WHERE user_id=%s AND embedding_backend=%s",
                (user_id, backend),
            )
            rows = cursor.fetchall()
        return {row[0]: self._parse_vector(row[1]) for row in rows}

    def save_profile(self, profile: MatchProfile) -> None:
        self._ensure_schema()
        from psycopg.types.json import Jsonb
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO matching_profiles
                   (user_id, display_name, interests, communication_preferences, embedding, embedding_backend, last_active_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s::extensions.vector,%s,%s,now())
                   ON CONFLICT (user_id) DO UPDATE SET display_name=EXCLUDED.display_name,
                   interests=EXCLUDED.interests, communication_preferences=EXCLUDED.communication_preferences,
                   embedding=EXCLUDED.embedding, embedding_backend=EXCLUDED.embedding_backend,
                   last_active_at=EXCLUDED.last_active_at, updated_at=now()""",
                (profile.user_id, profile.display_name, Jsonb(profile.interests), Jsonb(profile.communication_preferences),
                 self._vector(profile.embedding), profile.embedding_backend, profile.last_active_at),
            )
            for interest, embedding in profile.interest_embeddings.items():
                cursor.execute(
                    """INSERT INTO matching_interest_embeddings
                       (user_id,interest,embedding,embedding_backend,updated_at)
                       VALUES (%s,%s,%s::extensions.vector,%s,now())
                       ON CONFLICT (user_id,interest) DO UPDATE SET embedding=EXCLUDED.embedding,
                       embedding_backend=EXCLUDED.embedding_backend,updated_at=now()""",
                    (profile.user_id, interest, self._vector(embedding), profile.embedding_backend),
                )

    def list_profiles(self) -> list[MatchProfile]:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT user_id,display_name,interests,communication_preferences,embedding::text,embedding_backend,last_active_at FROM matching_profiles")
            rows = cursor.fetchall()
            cursor.execute("SELECT user_id,interest,embedding::text,embedding_backend FROM matching_interest_embeddings")
            interest_rows = cursor.fetchall()
        by_user: dict[str, dict[str, list[float]]] = {}
        for owner, interest, embedding, backend in interest_rows:
            by_user.setdefault(owner, {})[interest] = self._parse_vector(embedding)
        return [
            MatchProfile(
                row[0], row[1], list(row[2]), list(row[3]),
                {interest: vector for interest, vector in by_user.get(row[0], {}).items() if interest in set(row[2])},
                self._parse_vector(row[4]), row[5], row[6].isoformat(),
            )
            for row in rows
        ]

    def save_match(self, match: dict[str, Any]) -> None:
        self._ensure_schema()
        from psycopg.types.json import Jsonb
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO match_candidates (match_id,user_a,user_b,score,reasons,features,status,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,'pending',now())
                   ON CONFLICT (match_id) DO UPDATE SET score=EXCLUDED.score,reasons=EXCLUDED.reasons,
                   features=EXCLUDED.features,updated_at=now()""",
                (match["match_id"], match["user_a"], match["user_b"], match["score"], Jsonb(match["reasons"]), Jsonb(match["features"])),
            )
            for viewer, candidate in ((match["user_a"], match["user_b"]), (match["user_b"], match["user_a"])):
                cursor.execute(
                    """INSERT INTO match_impressions (match_id,viewer_id,candidate_id,features)
                       VALUES (%s,%s,%s,%s) ON CONFLICT (match_id,viewer_id) DO UPDATE SET features=EXCLUDED.features""",
                    (match["match_id"], viewer, candidate, Jsonb(match["features"][viewer])),
                )

    def _rows(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT match_id,user_a,user_b,score,reasons,features,status,decisions,
                          connected_at,disconnected_at FROM match_candidates m
                   WHERE %s IN (user_a,user_b)
                   AND NOT EXISTS (SELECT 1 FROM blocked_users b WHERE
                     (b.blocker_id=%s AND b.blocked_id=CASE WHEN m.user_a=%s THEN m.user_b ELSE m.user_a END)
                     OR (b.blocked_id=%s AND b.blocker_id=CASE WHEN m.user_a=%s THEN m.user_b ELSE m.user_a END))
                   ORDER BY score DESC""",
                (user_id, user_id, user_id, user_id, user_id),
            )
            rows = cursor.fetchall()
        return [{"match_id": r[0], "user_a": r[1], "user_b": r[2], "score": float(r[3]),
                 "reasons": list(r[4]), "features": dict(r[5]), "status": r[6], "decisions": dict(r[7]),
                 "connected_at": r[8].isoformat() if r[8] else None,
                 "disconnected_at": r[9].isoformat() if r[9] else None} for r in rows]

    def list_matches(self, user_id: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._rows(user_id)

    def get_match(self, match_id: str) -> dict[str, Any]:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT user_a FROM match_candidates WHERE match_id=%s", (match_id,))
            row = cursor.fetchone()
        if not row:
            return {}
        return next((item for item in self._rows(row[0]) if item["match_id"] == match_id), {})

    def save_decision(self, match_id: str, user_id: str, decision: str) -> dict[str, Any]:
        self._ensure_schema()
        from psycopg.types.json import Jsonb
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT user_a,user_b,decisions FROM match_candidates WHERE match_id=%s FOR UPDATE", (match_id,))
            row = cursor.fetchone()
            if not row or user_id not in {row[0], row[1]}:
                raise ValueError("Match not found.")
            user_a, user_b, decisions = row[0], row[1], dict(row[2] or {})
            other = user_b if user_a == user_id else user_a
            decisions[user_id] = decision
            status = "blocked" if decision == "block" else "passed" if decision == "pass" else "connected" if decisions.get(other) == "accept" else "pending"
            cursor.execute("INSERT INTO match_decisions (match_id,user_id,decision) VALUES (%s,%s,%s) ON CONFLICT (match_id,user_id) DO UPDATE SET decision=EXCLUDED.decision,created_at=now()", (match_id,user_id,decision))
            cursor.execute("UPDATE match_candidates SET decisions=%s,status=%s,updated_at=now(),connected_at=CASE WHEN %s='connected' THEN now() ELSE connected_at END WHERE match_id=%s", (Jsonb(decisions),status,status,match_id))
            if status == "connected":
                cursor.execute("INSERT INTO connections (match_id,user_a,user_b) VALUES (%s,%s,%s) ON CONFLICT (match_id) DO UPDATE SET disconnected_at=NULL", (match_id,user_a,user_b))
            if decision == "block":
                cursor.execute("INSERT INTO blocked_users (blocker_id,blocked_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user_id,other))
        return {"match_id": match_id, "user_a": user_a, "user_b": user_b, "status": status, "decisions": decisions}

    def block(self, blocker_id: str, blocked_id: str) -> None:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO blocked_users (blocker_id,blocked_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (blocker_id,blocked_id))

    def disconnect(self, match_id: str, user_id: str) -> None:
        self._ensure_schema()
        match = self.get_match(match_id)
        if not match or user_id not in {match["user_a"], match["user_b"]}:
            raise ValueError("Connection not found.")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE match_candidates SET status='disconnected',disconnected_at=now(),updated_at=now() WHERE match_id=%s", (match_id,))
            cursor.execute("UPDATE connections SET disconnected_at=now() WHERE match_id=%s", (match_id,))

    def get_model(self, user_id: str) -> dict[str, Any]:
        self._ensure_schema()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT weights,decision_count FROM ranking_models WHERE user_id=%s", (user_id,))
            row = cursor.fetchone()
        return {"weights": list(row[0]), "decision_count": row[1]} if row else {}

    def save_model(self, user_id: str, weights: list[float], decision_count: int) -> None:
        self._ensure_schema()
        from psycopg.types.json import Jsonb
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO ranking_models (user_id,weights,decision_count) VALUES (%s,%s,%s) ON CONFLICT (user_id) DO UPDATE SET weights=EXCLUDED.weights,decision_count=EXCLUDED.decision_count,updated_at=now()", (user_id,Jsonb(weights),decision_count))


class MatchingEngine:
    def __init__(
        self,
        memory: Any,
        repository: MatchingRepository,
        embedder: Embedder,
        interest_embedder: InterestEmbeddingProvider | None = None,
    ) -> None:
        self.memory = memory
        self.repository = repository
        self.embedder = embedder
        self.local_interest_embedder = LocalInterestEmbeddingProvider(embedder)
        self.interest_embedder = interest_embedder or self.local_interest_embedder

    def _safe_profile(self, account: dict[str, Any]) -> MatchProfile:
        user_id = str(account["user_id"])
        memory_profile = self.memory.profile(user_id)
        interests = _clean_values([
            item.get("topic", "") for item in memory_profile.get("interests", [])
            if isinstance(item, dict) and item.get("current_polarity") == "positive"
        ])
        communication = _clean_values(memory_profile.get("communication_preferences", []))
        cached = self.repository.get_interest_embeddings(user_id, self.interest_embedder.name)
        missing = [interest for interest in interests if interest not in cached]
        backend = self.interest_embedder.name
        try:
            generated = self.interest_embedder.embed_many(missing)
            interest_embeddings = {interest: cached.get(interest) or generated[interest] for interest in interests}
        except (httpx.HTTPError, KeyError, RuntimeError, ValueError):
            # Conversation remains available if the embedding API is temporarily
            # unavailable. The next refresh retries the semantic provider.
            backend = self.local_interest_embedder.name
            interest_embeddings = self.local_interest_embedder.embed_many(interests)
        return MatchProfile(
            user_id=user_id,
            display_name=str(account.get("display_name") or "RSpace member")[:80],
            interests=interests,
            communication_preferences=communication,
            interest_embeddings=interest_embeddings,
            embedding=_mean_vector(list(interest_embeddings.values())),
            embedding_backend=backend,
            last_active_at=str(account.get("updated_at") or _now()),
        )

    def refresh_profiles(self) -> None:
        for account in self.memory.store.list_account_profiles():
            self.repository.save_profile(self._safe_profile(account))

    def _shared(self, left: MatchProfile, right: MatchProfile) -> list[str]:
        choices: list[tuple[float, str, str]] = []
        for first in left.interests:
            first_embedding = left.interest_embeddings.get(first, [])
            for second in right.interests:
                score = cosine_similarity(first_embedding, right.interest_embeddings.get(second, []))
                if first == second or score >= INTEREST_SIMILARITY_THRESHOLD:
                    choices.append((1.0 if first == second else score, first, second))
        shared: list[str] = []
        used_right: set[str] = set()
        for _, first, second in sorted(choices, reverse=True):
            if first in shared or second in used_right:
                continue
            shared.append(first)
            used_right.add(second)
        return shared

    def _features(self, left: MatchProfile, right: MatchProfile, shared: list[str]) -> list[float]:
        semantic = max(0.0, cosine_similarity(left.embedding, right.embedding))
        shared_ratio = len(shared) / max(len(left.interests), len(right.interests), 1)
        left_comm, right_comm = set(left.communication_preferences), set(right.communication_preferences)
        communication = len(left_comm & right_comm) / len(left_comm | right_comm) if left_comm | right_comm else 0.5
        return [1.0, semantic, shared_ratio, communication]

    @staticmethod
    def _is_active(profile: MatchProfile) -> bool:
        try:
            last_active = datetime.fromisoformat(profile.last_active_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_active <= ACTIVE_WINDOW

    def _predict(self, user_id: str, features: list[float], fallback: float) -> float:
        model = self.repository.get_model(user_id)
        if int(model.get("decision_count", 0)) < MIN_LEARNING_DECISIONS:
            return fallback
        weights = [float(value) for value in model.get("weights", [])]
        if len(weights) != len(features):
            return fallback
        return _sigmoid(sum(weight * feature for weight, feature in zip(weights, features)))

    def _train(self, user_id: str, features: list[float], label: float) -> None:
        model = self.repository.get_model(user_id)
        weights = [float(value) for value in model.get("weights", [0.0] * MODEL_FEATURES)]
        if len(weights) != MODEL_FEATURES:
            weights = [0.0] * MODEL_FEATURES
        for _ in range(12):
            prediction = _sigmoid(sum(weight * feature for weight, feature in zip(weights, features)))
            for index, feature in enumerate(features):
                weights[index] += 0.12 * ((label - prediction) * feature - 0.002 * weights[index])
        self.repository.save_model(user_id, weights, int(model.get("decision_count", 0)) + 1)

    def _ensure_demo_request(self, user_id: str, profiles: dict[str, MatchProfile]) -> None:
        """Create one idempotent, pre-accepted demo request for the hackathon account."""
        account = self.memory.store.load_account_profile(user_id)
        email_hash = hashlib.sha256(str(account.get("email") or "").lower().encode()).hexdigest()
        if email_hash != DEMO_MATCH_TARGET_EMAIL_HASH:
            return
        target = profiles.get(user_id)
        if not target:
            return

        interest = target.interests[0] if target.interests else "friendly conversation"
        vector = target.interest_embeddings.get(interest) or self.local_interest_embedder.embed_many([interest])[interest]
        demo = MatchProfile(
            user_id=DEMO_MATCH_USER_ID,
            display_name=DEMO_MATCH_NAME,
            interests=[interest],
            communication_preferences=[],
            interest_embeddings={interest: vector},
            embedding=vector,
            embedding_backend=self.local_interest_embedder.name,
            last_active_at=_now(),
        )
        self.memory.store.save_account_profile(
            DEMO_MATCH_USER_ID, DEMO_MATCH_EMAIL, DEMO_MATCH_NAME
        )
        self.repository.save_profile(demo)
        profiles[DEMO_MATCH_USER_ID] = demo

        first, second = sorted((user_id, DEMO_MATCH_USER_ID))
        match_id = _pair_id(first, second)
        existing = self.repository.get_match(match_id)
        if existing and existing.get("status") != "pending":
            return

        target_features = self._features(target, demo, [interest])
        demo_features = self._features(demo, target, [interest])
        self.repository.save_match({
            "match_id": match_id,
            "user_a": first,
            "user_b": second,
            "score": 0.93,
            "reasons": [interest],
            "features": {user_id: target_features, DEMO_MATCH_USER_ID: demo_features},
            "status": "pending",
            "decisions": {},
            "created_at": _now(),
            "updated_at": _now(),
        })
        current = self.repository.get_match(match_id)
        if current.get("decisions", {}).get(DEMO_MATCH_USER_ID) != "accept":
            self.repository.save_decision(match_id, DEMO_MATCH_USER_ID, "accept")

    def find_matches(self, user_id: str) -> list[dict[str, Any]]:
        self.refresh_profiles()
        profiles = {profile.user_id: profile for profile in self.repository.list_profiles()}
        if user_id not in profiles:
            return []
        self._ensure_demo_request(user_id, profiles)
        current = profiles[user_id]
        pair_data: dict[tuple[str, str], tuple[list[str], float]] = {}
        neighbors: dict[str, list[tuple[str, float]]] = {profile_id: [] for profile_id in profiles}
        profile_list = list(profiles.values())
        for index, left in enumerate(profile_list):
            for right in profile_list[index + 1:]:
                if not self._is_active(left) or not self._is_active(right):
                    continue
                shared = self._shared(left, right)
                if len(shared) < MIN_SHARED_INTERESTS:
                    continue
                semantic = max(0.0, cosine_similarity(left.embedding, right.embedding))
                key = tuple(sorted((left.user_id, right.user_id)))
                pair_data[key] = (shared, semantic)
                neighbors[left.user_id].append((right.user_id, semantic))
                neighbors[right.user_id].append((left.user_id, semantic))
        ranks: dict[tuple[str, str], int] = {}
        for owner, candidates in neighbors.items():
            for rank, (candidate, _) in enumerate(sorted(candidates, key=lambda item: item[1], reverse=True), start=1):
                ranks[(owner, candidate)] = rank

        for other_id, other in profiles.items():
            key = tuple(sorted((user_id, other_id)))
            if other_id == user_id or key not in pair_data:
                continue
            shared, semantic = pair_data[key]
            features = self._features(current, other, shared)
            reciprocal_rank = math.sqrt(ranks[(user_id, other_id)] * ranks[(other_id, user_id)])
            rank_strength = 1.0 / reciprocal_rank
            # Shared interests are strong cold-start evidence. The saturating
            # curve rewards additional overlap while still allowing a single
            # strong shared interest to produce a match.
            shared_evidence = 1.0 - math.exp(-len(shared))
            match_quality = max(semantic, shared_evidence)
            cold_score = math.sqrt(match_quality * rank_strength)
            reverse_features = self._features(other, current, shared)
            left_probability = self._predict(user_id, features, cold_score)
            right_probability = self._predict(other_id, reverse_features, cold_score)
            score = math.sqrt(left_probability * right_probability)
            if score < MATCH_THRESHOLD:
                continue
            first, second = sorted((user_id, other_id))
            self.repository.save_match({
                "match_id": _pair_id(first, second), "user_a": first, "user_b": second,
                "score": round(score, 4), "reasons": shared[:3],
                "features": {user_id: features, other_id: reverse_features}, "status": "pending",
                "decisions": {}, "created_at": _now(), "updated_at": _now(),
            })
        return self._public_matches(user_id, profiles)

    def _public_matches(self, user_id: str, profiles: dict[str, MatchProfile] | None = None) -> list[dict[str, Any]]:
        profiles = profiles or {profile.user_id: profile for profile in self.repository.list_profiles()}
        results = []
        for match in self.repository.list_matches(user_id):
            if match.get("status") != "pending":
                continue
            other_id = match["user_b"] if match["user_a"] == user_id else match["user_a"]
            other = profiles.get(other_id)
            if not other:
                continue
            decisions = match.get("decisions", {})
            results.append({
                "match_id": match["match_id"], "name": other.display_name,
                "score": round(float(match["score"]) * 100), "shared_interests": match.get("reasons", []),
                "why": self._reason(match.get("reasons", [])), "status": match.get("status"),
                "your_decision": decisions.get(user_id),
            })
        return results

    @staticmethod
    def _reason(shared: list[str]) -> str:
        concise = shared[:2]
        if len(concise) == 1:
            return f"You both mentioned {concise[0]}."
        return f"You both mentioned {concise[0]} and {concise[1]}."

    def decide(self, user_id: str, match_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accept", "pass", "block"}:
            raise ValueError("Decision must be accept, pass, or block.")
        match = self.repository.get_match(match_id)
        if not match or user_id not in {match.get("user_a"), match.get("user_b")}:
            raise ValueError("Match not found.")
        features = match.get("features", {}).get(user_id, [])
        if len(features) == MODEL_FEATURES:
            self._train(user_id, [float(value) for value in features], 1.0 if decision == "accept" else 0.0)
        updated = self.repository.save_decision(match_id, user_id, decision)
        return {"match_id": match_id, "status": updated.get("status"), "decision": decision}

    def connections(self, user_id: str) -> list[dict[str, Any]]:
        profiles = {profile.user_id: profile for profile in self.repository.list_profiles()}
        connections = []
        for match in self.repository.list_matches(user_id):
            if match.get("status") != "connected":
                continue
            other_id = match["user_b"] if match["user_a"] == user_id else match["user_a"]
            other = profiles.get(other_id)
            account = self.memory.store.load_account_profile(other_id)
            if other and account:
                connections.append({"match_id": match["match_id"], "name": other.display_name, "email": account.get("email", ""), "why": self._reason(match.get("reasons", []))})
        return connections

    def disconnect(self, user_id: str, match_id: str) -> None:
        match = self.repository.get_match(match_id)
        if match and user_id in {match.get("user_a"), match.get("user_b")}:
            features = match.get("features", {}).get(user_id, [])
            if len(features) == MODEL_FEATURES:
                self._train(user_id, [float(value) for value in features], 0.0)
        self.repository.disconnect(match_id, user_id)


def create_matching_engine(memory: Any, data_root: Path) -> MatchingEngine:
    database_url = os.getenv("DATABASE_URL", "").strip()
    repository: MatchingRepository = PostgresMatchingRepository(database_url) if database_url else JsonMatchingRepository(data_root)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    interest_embedder: InterestEmbeddingProvider = (
        OpenAIInterestEmbeddingProvider(api_key, model) if api_key and not api_key.startswith("your_")
        else LocalInterestEmbeddingProvider(memory.embedder)
    )
    return MatchingEngine(memory, repository, memory.embedder, interest_embedder)
