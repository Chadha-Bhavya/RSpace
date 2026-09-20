from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FilterResult:
    redacted_text: str
    safety_flags: list[str] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)


@dataclass
class MemoryDraft:
    kind: str
    value: str
    confidence: float
    evidence: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEvent:
    event_id: str
    user_id: str
    timestamp: str
    kind: str
    value: str
    confidence: float
    evidence: str
    attributes: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    embedding_backend: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEvent":
        return cls(
            event_id=str(data["event_id"]),
            user_id=str(data["user_id"]),
            timestamp=str(data["timestamp"]),
            kind=str(data["kind"]),
            value=str(data["value"]),
            confidence=float(data.get("confidence", 0.0)),
            evidence=str(data.get("evidence", "")),
            attributes=dict(data.get("attributes", {})),
            embedding=[float(value) for value in data.get("embedding", [])],
            embedding_backend=str(data.get("embedding_backend", "")),
        )
