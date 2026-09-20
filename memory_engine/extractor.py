from __future__ import annotations

import re

from .models import MemoryDraft


INTEREST_TERMS: dict[str, tuple[str, ...]] = {
    "gardening": ("garden", "gardening", "flowers", "growing vegetables"),
    "music": ("music", "piano", "guitar", "singing", "choir"),
    "jazz": ("jazz",),
    "reading": ("reading", "read books", "book club", "novels"),
    "walking": ("walking", "go for walks", "hiking"),
    "cooking": ("cooking", "baking", "cook", "bake"),
    "sports": ("basketball", "baseball", "football", "soccer", "tennis", "golf"),
    "cards_and_games": ("bridge", "chess", "bingo", "cards", "board games"),
    "travel": ("travel", "traveling", "trips", "vacation"),
    "pets": ("dog", "cat", "pet", "puppy", "kitten"),
    "movies_and_tv": ("movies", "films", "television", "watching tv"),
    "art": ("painting", "drawing", "art", "crafts", "knitting", "sewing"),
    "community": ("church", "temple", "community center", "volunteering", "volunteer"),
}

RELATIONSHIPS = (
    "wife", "husband", "partner", "daughter", "son", "sister", "brother",
    "granddaughter", "grandson", "grandchildren", "grandkids", "friend", "neighbor",
)

LONELINESS_TERMS = ("lonely", "isolated", "alone", "nobody to talk to", "no one to talk to")
CONNECTION_TERMS = ("called me", "visited me", "spent time with", "talked with", "saw my", "met with")
NEGATION_MARKERS = ("not", "never", "no longer", "don't", "do not", "didn't", "did not", "hardly")
FORMER_MARKERS = ("used to", "no longer", "back when", "haven't in a while", "miss doing")
FREQUENT_MARKERS = ("every day", "every week", "regularly", "often", "always", "still love")
OCCASIONAL_MARKERS = ("sometimes", "occasionally", "now and then", "once in a while")

STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before", "being",
    "but", "can", "could", "did", "does", "doing", "for", "from", "had", "has", "have",
    "her", "here", "him", "his", "how", "into", "just", "like", "more", "much", "myself",
    "not", "now", "our", "out", "really", "said", "she", "should", "some", "than", "that",
    "the", "their", "them", "then", "there", "they", "this", "today", "too", "very", "was",
    "were", "what", "when", "where", "which", "while", "who", "will", "with", "would", "you",
    "your", "redacted", "phone", "email", "address", "card", "ssn", "name",
}

SMALL_TALK = {
    "hello", "hi", "hey", "okay", "ok", "yes", "no", "thanks", "thank you",
    "how are you", "good morning", "good afternoon", "good evening", "good night",
}


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _has_negation(sentence: str, phrase: str) -> bool:
    lower = sentence.lower()
    start = lower.find(phrase.lower())
    if start < 0:
        return False
    prefix = lower[max(0, start - 45):start]
    return any(re.search(rf"\b{re.escape(marker)}\b", prefix) for marker in NEGATION_MARKERS)


def _strength(sentence: str) -> str:
    lower = sentence.lower()
    if any(marker in lower for marker in FORMER_MARKERS):
        return "former"
    if any(marker in lower for marker in FREQUENT_MARKERS):
        return "frequent"
    if any(marker in lower for marker in OCCASIONAL_MARKERS):
        return "occasional"
    return "unknown"


def _keywords(sentence: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9' ]", " ", sentence.lower())
    if " ".join(normalized.split()) in SMALL_TALK:
        return []
    words = [word for word in normalized.split() if len(word) > 2 and word not in STOPWORDS]
    unique: list[str] = []
    for word in words:
        if word not in unique:
            unique.append(word)
    return unique[:8]


def extract_memories(text: str) -> list[MemoryDraft]:
    """Extract transparent, rule-based memories without an LLM call."""
    drafts: list[MemoryDraft] = []
    for sentence in _sentences(text):
        lower = sentence.lower()

        for topic, terms in INTEREST_TERMS.items():
            matched = next((term for term in terms if re.search(rf"\b{re.escape(term)}\b", lower)), None)
            if not matched:
                continue
            negated = _has_negation(sentence, matched)
            drafts.append(MemoryDraft(
                kind="interest",
                value=topic,
                confidence=0.9 if not negated else 0.88,
                evidence=sentence,
                attributes={
                    "polarity": "negative" if negated else "positive",
                    "strength": "none" if negated else _strength(sentence),
                },
            ))

        for relationship in RELATIONSHIPS:
            if re.search(rf"\b(?:my\s+)?{re.escape(relationship)}s?\b", lower):
                drafts.append(MemoryDraft(
                    kind="relationship",
                    value=relationship,
                    confidence=0.82,
                    evidence=sentence,
                    attributes={},
                ))

        for term in LONELINESS_TERMS:
            if term in lower:
                drafts.append(MemoryDraft(
                    kind="social_signal",
                    value="loneliness",
                    confidence=0.9,
                    evidence=sentence,
                    attributes={"polarity": "negative" if _has_negation(sentence, term) else "positive"},
                ))
                break

        if any(term in lower for term in CONNECTION_TERMS):
            drafts.append(MemoryDraft(
                kind="social_signal",
                value="social_connection",
                confidence=0.78,
                evidence=sentence,
                attributes={"polarity": "positive"},
            ))

        for time_name in ("morning", "afternoon", "evening", "weekend"):
            if time_name in lower and any(word in lower for word in ("free", "available", "prefer", "usually")):
                drafts.append(MemoryDraft(
                    kind="availability",
                    value=time_name,
                    confidence=0.75,
                    evidence=sentence,
                ))

        for mode in ("voice", "video", "text"):
            if re.search(rf"\b(?:prefer|like)\s+(?:to\s+)?{mode}\b", lower):
                drafts.append(MemoryDraft(
                    kind="communication_preference",
                    value=mode,
                    confidence=0.8,
                    evidence=sentence,
                ))

        # Preserve useful information outside the curated categories. These
        # evidence-backed notes make the engine useful immediately while the
        # deterministic taxonomy grows over time.
        keywords = _keywords(sentence)
        if len(keywords) >= 2:
            drafts.append(MemoryDraft(
                kind="conversation_note",
                value=" ".join(keywords[:4]),
                confidence=0.68,
                evidence=sentence,
                attributes={"keywords": keywords},
            ))

    return drafts
