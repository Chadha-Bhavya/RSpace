"""
Validation layer — decides what to trust from an extraction, guards
against fabricated information, and decides when a follow-up question is
worth asking.

This is deliberately plain, deterministic Python. The LLM proposes
interests and confidence scores; the *decisions* about what to keep,
discard, or ask about again live entirely here, not inside a prompt.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from extraction import ExtractorClient
from models import CommMode, ExtractedInterest, FieldValue, InterestStrength, TimeBlock, UserProfile

# Below this confidence, we don't trust the extraction enough to store it.
MIN_CONFIDENCE_TO_STORE = 0.35
# Below this, we store it but consider it worth a clarifying follow-up.
MIN_CONFIDENCE_CONFIDENT = 0.7
# Don't interrogate someone about every single thing they say in one turn.
MAX_CLARIFICATIONS_PER_TURN = 1


def _is_grounded(source_phrase: str, raw_text: str) -> bool:
    """Lightweight anti-hallucination guard: the phrase the extractor
    claims something came from should actually appear in what the user
    said. This won't catch a very creative fabrication, but it reliably
    filters out the common failure mode of an LLM inventing a detail
    that was never in the input at all."""
    if not source_phrase:
        return False
    phrase_words = set(re.findall(r"[a-z]+", source_phrase.lower()))
    text_words = set(re.findall(r"[a-z]+", raw_text.lower()))
    if not phrase_words:
        return False
    overlap = len(phrase_words & text_words) / len(phrase_words)
    return overlap >= 0.6


def apply_extraction(
    profile: UserProfile,
    raw_text: str,
    extraction: Dict[str, Any],
    client: ExtractorClient,
) -> List[str]:
    """Merges one extraction result into `profile`, applying validation
    rules along the way. Returns a list of clarification questions the
    conversation layer should ask next (may be empty).
    """
    profile.raw_statements.append(raw_text)
    clarifications: List[str] = []

    for item in extraction.get("interests", []) or []:
        try:
            interest = ExtractedInterest(
                topic=str(item["topic"]).strip().lower().replace(" ", "_"),
                strength=InterestStrength(item.get("strength", "unknown")),
                confidence=float(item.get("confidence", 0.5)),
                source_phrase=str(item.get("source_phrase", "")),
            )
        except (KeyError, ValueError, TypeError):
            continue  # malformed item from the model — skip rather than guess

        if not _is_grounded(interest.source_phrase, raw_text):
            continue  # can't verify this was actually said — drop it, don't store it

        if interest.confidence < MIN_CONFIDENCE_TO_STORE:
            continue  # too uncertain to be useful for matching

        profile.upsert_interest(interest)

        needs_clarification = (
            interest.strength == InterestStrength.UNKNOWN
            or interest.confidence < MIN_CONFIDENCE_CONFIDENT
        )
        if needs_clarification and len(clarifications) < MAX_CLARIFICATIONS_PER_TURN:
            clarifications.append(client.generate_clarification(interest.topic, raw_text))

    location = extraction.get("location")
    if location:
        profile.location = FieldValue(value=str(location).strip().title(), confidence=0.75)

    for lang in extraction.get("languages", []) or []:
        profile.languages.add(str(lang).strip().lower())

    for block in extraction.get("availability", []) or []:
        try:
            profile.availability.add(TimeBlock(block))
        except ValueError:
            continue  # unrecognized value from the model — ignore rather than crash

    comm_mode = extraction.get("preferred_comm_mode")
    if comm_mode:
        try:
            profile.preferred_comm_mode = CommMode(comm_mode)
        except ValueError:
            pass

    for note in extraction.get("background_notes", []) or []:
        note = note.strip()
        if note and note not in profile.background_notes:
            profile.background_notes.append(note)

    profile.pending_clarifications = clarifications
    return clarifications