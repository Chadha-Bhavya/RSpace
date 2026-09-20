from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .embeddings import Embedder, create_embedder
from .elastic import ElasticsearchMemoryIndex, create_elasticsearch_index
from .extractor import MemoryExtractor, create_extractor
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
        extractor: MemoryExtractor | None = None,
        elastic_index: ElasticsearchMemoryIndex | None = None,
    ) -> None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        self.store: MemoryStore = store or (
            PostgresMemoryStore(database_url) if database_url else JsonlMemoryStore(data_root)
        )
        self.embedder = embedder or create_embedder()
        self.extractor = extractor or create_extractor()
        self.elastic_index = elastic_index or create_elasticsearch_index()

    def process(self, user_id: str, transcript: str) -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        filtered = filter_text(transcript)
        drafts = validate_drafts(filtered.redacted_text, self.extractor.extract(filtered.redacted_text))
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
        if self.elastic_index:
            try:
                self.elastic_index.index_events(events)
            except Exception:
                # Elastic is a secondary index. Never lose a memory or stop a conversation
                # because it is unavailable.
                pass
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
            "extraction_backend": self.extractor.name,
        }

    def profile(self, user_id: str) -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        profile = self.store.load_profile(user_id)
        if profile:
            return profile
        profile = build_profile(user_id, self.store.load_events(user_id), self.embedder.name)
        self.store.save_profile(user_id, profile)
        return profile

    def search(
        self, user_id: str, query: str, limit: int = 5,
        category: str | None = None, date_from: str | None = None, date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        user_id = self.store.safe_user_id(user_id)
        limit = max(1, min(limit, 20))
        if self.elastic_index:
            try:
                results = self.elastic_index.search(
                    user_id, query, self.embedder.embed(query), limit, category, date_from, date_to
                )
                if results:
                    return results
            except Exception:
                pass
        events = self.store.load_events(user_id)
        if category:
            events = [event for event in events if event.kind == category]
        if date_from:
            events = [event for event in events if event.timestamp >= date_from]
        if date_to:
            events = [event for event in events if event.timestamp <= date_to]
        return hybrid_search(query, events, self.embedder, limit)

    def report(self, user_id: str) -> dict[str, Any]:
        return build_wellness_report(self.profile(user_id))

    def start_conversation(self, user_id: str, timezone_name: str = "UTC") -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        return self.store.start_conversation(user_id, timezone_name)

    def conversation_context(self, user_id: str, session_id: str) -> dict[str, Any]:
        user_id = self.store.safe_user_id(user_id)
        return self.store.conversation_context(user_id, session_id)

    def save_conversation_turns(
        self, user_id: str, session_id: str, user_text: str, assistant_text: str
    ) -> None:
        user_id = self.store.safe_user_id(user_id)
        safe_user_text = filter_text(user_text).redacted_text
        safe_assistant_text = filter_text(assistant_text).redacted_text
        self.store.save_conversation_turns(user_id, session_id, [
            {"role": "user", "content": safe_user_text},
            {"role": "assistant", "content": safe_assistant_text},
        ])

    def touch_conversation(self, user_id: str, session_id: str) -> None:
        user_id = self.store.safe_user_id(user_id)
        self.store.touch_conversation(user_id, session_id)

    def end_conversation(self, user_id: str, session_id: str) -> None:
        user_id = self.store.safe_user_id(user_id)
        self.store.end_conversation(user_id, session_id)

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
