"""
Data model for the senior social-matching system.

Every field exists because the matching algorithm (matching.py) actually
uses it — nothing is here "just in case."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set


class InterestStrength(str, Enum):
    """How engaged the person currently is with an interest. This is the
    piece that distinguishes 'I used to play tennis' from 'I play tennis
    every week' — same topic, very different matching weight."""
    FREQUENT = "frequent"      # "every week", "still love", "regularly"
    OCCASIONAL = "occasional"  # "sometimes", "now and then"
    FORMER = "former"          # "I used to...", "haven't in a while"
    UNKNOWN = "unknown"        # mentioned, but engagement level unclear


class TimeBlock(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    WEEKEND = "weekend"


class CommMode(str, Enum):
    VOICE = "voice"
    VIDEO = "video"
    TEXT = "text"


# How much each strength level counts toward a match. Frequent, current
# engagement counts most; former/unstated interests still count for
# something (people bond over "I used to do that too!") but less.
STRENGTH_WEIGHT: Dict[InterestStrength, float] = {
    InterestStrength.FREQUENT: 1.0,
    InterestStrength.OCCASIONAL: 0.75,
    InterestStrength.FORMER: 0.5,
    InterestStrength.UNKNOWN: 0.6,
}


@dataclass
class ExtractedInterest:
    """One interest extracted from something the user said."""
    topic: str                                  # canonical tag, e.g. "gardening"
    strength: InterestStrength = InterestStrength.UNKNOWN
    confidence: float = 0.5                      # extractor's confidence, 0-1
    source_phrase: str = ""                      # the exact words this came from
                                                   # (kept for explainability AND so
                                                   # validation.py can check the
                                                   # extraction wasn't fabricated)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "source_phrase": self.source_phrase,
        }


@dataclass
class FieldValue:
    """A single extracted scalar field (currently just location) paired
    with how confident we are in it."""
    value: str
    confidence: float = 0.5


@dataclass
class UserProfile:
    """The structured record for one senior user. JSON-serializable via
    to_dict() so it can be dropped straight into a database or an API
    response."""
    user_id: str
    name: Optional[str] = None
    location: Optional[FieldValue] = None
    languages: Set[str] = field(default_factory=set)
    interests: Dict[str, ExtractedInterest] = field(default_factory=dict)  # topic -> interest
    availability: Set[TimeBlock] = field(default_factory=set)
    preferred_comm_mode: Optional[CommMode] = None
    background_notes: List[str] = field(default_factory=list)   # icebreaker material
    pending_clarifications: List[str] = field(default_factory=list)  # follow-ups to ask next
    raw_statements: List[str] = field(default_factory=list)     # audit trail
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def upsert_interest(self, interest: ExtractedInterest) -> None:
        """Merge a newly-extracted interest into the profile. If we
        already have this topic, keep whichever observation we're more
        confident about rather than blindly overwriting with the latest
        one — a confident answer shouldn't be erased by a vaguer one."""
        existing = self.interests.get(interest.topic)
        if existing is None or interest.confidence >= existing.confidence:
            self.interests[interest.topic] = interest

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "location": (
                {"value": self.location.value, "confidence": self.location.confidence}
                if self.location else None
            ),
            "languages": sorted(self.languages),
            "interests": [i.to_dict() for i in self.interests.values()],
            "availability": sorted(t.value for t in self.availability),
            "preferred_comm_mode": self.preferred_comm_mode.value if self.preferred_comm_mode else None,
            "background_notes": self.background_notes,
            "pending_clarifications": self.pending_clarifications,
        }


@dataclass
class MatchResult:
    other_user_id: str
    score: float                     # 0.0 - 1.0
    breakdown: Dict[str, float]      # dimension -> contribution
    shared_interests: List[str]
    explanation: str