from __future__ import annotations

from .models import MemoryDraft


ALLOWED_KINDS = {
    "interest", "relationship", "social_signal", "availability", "communication_preference",
    "conversation_note",
    "important_date", "plan",
}
MIN_CONFIDENCE = 0.55


def validate_drafts(redacted_text: str, drafts: list[MemoryDraft]) -> list[MemoryDraft]:
    """Keep only grounded, well-formed extraction results."""
    accepted: list[MemoryDraft] = []
    seen: set[tuple[str, str, str]] = set()
    for draft in drafts:
        if draft.kind not in ALLOWED_KINDS or not draft.value.strip():
            continue
        if not 0 <= draft.confidence <= 1 or draft.confidence < MIN_CONFIDENCE:
            continue
        if not draft.evidence or draft.evidence not in redacted_text:
            continue
        key = (draft.kind, draft.value, draft.evidence)
        if key in seen:
            continue
        seen.add(key)
        accepted.append(draft)
    return accepted
