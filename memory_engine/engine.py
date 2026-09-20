from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .embeddings import Embedder, create_embedder
from .extractor import extract_memories
from .filters import filter_text
from .models import MemoryDraft, MemoryEvent
from .profile import build_profile, build_wellness_report
from .retrieval import hybrid_search
from .store import JsonlMemoryStore, MemoryStore, PostgresMemoryStore
from .validation import validate_drafts


class MemoryEngine:
    def __init__(
        self,
        data_root: Path,
        embedder: Embedder | None = None,
        store: MemoryStore | None = None,
    ) -> None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        self.store: MemoryStore = store or (
            PostgresMemoryStore(database_url) if database_url else JsonlMemoryStore(data_root)
        )
        self.embedder = embedder or create_embedder()

    def process(self, user_id: str, transcript: str) -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        filtered = filter_text(transcript)
        drafts = validate_drafts(filtered.redacted_text, extract_memories(filtered.redacted_text))
        existing = self.store.load_events(user_id)
        now = datetime.now(timezone.utc)
        events: list[MemoryEvent] = []
        for draft in drafts:
            if self._is_recent_duplicate(draft, existing + events, now):
                continue
            timestamp = now.isoformat()
            event_id = hashlib.sha256(
                f"{user_id}|{timestamp}|{draft.kind}|{draft.value}|{draft.evidence}".encode("utf-8")
            ).hexdigest()[:20]
            embedding_text = f"{draft.kind}: {draft.value}. {draft.evidence}"
            events.append(MemoryEvent(
                event_id=event_id,
                user_id=user_id,
                timestamp=timestamp,
                kind=draft.kind,
                value=draft.value,
                confidence=draft.confidence,
                evidence=draft.evidence,
                attributes=draft.attributes,
                embedding=self.embedder.embed(embedding_text),
                embedding_backend=self.embedder.name,
            ))

        self.store.append_events(user_id, events)
        all_events = existing + events
        profile = build_profile(user_id, all_events, self.embedder.name)
        self.store.save_profile(user_id, profile)
        return {
            "stored_count": len(events),
            "stored_memories": [
                {"kind": event.kind, "value": event.value, "confidence": event.confidence}
                for event in events
            ],
            "duplicate_count": len(drafts) - len(events),
            "redactions": filtered.redactions,
            "safety_flags": filtered.safety_flags,
            "embedding_backend": self.embedder.name,
        }

    def profile(self, user_id: str) -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        profile = self.store.load_profile(user_id)
        if profile:
            return profile
        profile = build_profile(user_id, self.store.load_events(user_id), self.embedder.name)
        self.store.save_profile(user_id, profile)
        return profile

    def search(self, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        user_id = self.store.safe_user_id(user_id)
        return hybrid_search(query, self.store.load_events(user_id), self.embedder, max(1, min(limit, 20)))

    def report(self, user_id: str) -> dict[str, Any]:
        return build_wellness_report(self.profile(user_id))

    @staticmethod
    def _is_recent_duplicate(
        draft: MemoryDraft,
        events: list[MemoryEvent],
        now: datetime,
        duplicate_window: timedelta = timedelta(minutes=10),
    ) -> bool:
        for event in reversed(events[-100:]):
            if event.kind != draft.kind or event.value != draft.value or event.evidence != draft.evidence:
                continue
            try:
                timestamp = datetime.fromisoformat(event.timestamp)
            except ValueError:
                continue
            if now - timestamp <= duplicate_window:
                return True
        return False
