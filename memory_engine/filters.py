from __future__ import annotations

import re

from .models import FilterResult


PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("address", re.compile(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\s(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd)\b", re.I)),
    ("name", re.compile(r"\b(?:my name is|call me)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")),
]

SAFETY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "self_harm": (
        re.compile(r"\b(?:kill|hurt) myself\b", re.I),
        re.compile(r"\bdon't want to (?:live|be alive)\b", re.I),
        re.compile(r"\bsuicid(?:e|al)\b", re.I),
    ),
    "possible_abuse": (
        re.compile(r"\b(?:hits?|hurts?|threatens?) me\b", re.I),
        re.compile(r"\b(?:elder|financial) abuse\b", re.I),
    ),
    "medical_emergency": (
        re.compile(r"\bchest pain\b", re.I),
        re.compile(r"\bcan't breathe\b", re.I),
        re.compile(r"\b(?:having|had) a stroke\b", re.I),
        re.compile(r"\bmedical emergency\b", re.I),
    ),
}


def filter_text(text: str) -> FilterResult:
    """Redact common direct identifiers and flag explicit urgent language.

    This is deliberately conservative and explainable. It is a first privacy
    barrier, not a guarantee that all identifying information is removed.
    """
    cleaned = " ".join(text.strip().split())
    redactions: list[str] = []
    for label, pattern in PII_PATTERNS:
        cleaned, count = pattern.subn(f"[REDACTED_{label.upper()}]", cleaned)
        if count:
            redactions.extend([label] * count)

    safety_flags = [
        label
        for label, patterns in SAFETY_PATTERNS.items()
        if any(pattern.search(cleaned) for pattern in patterns)
    ]
    return FilterResult(
        redacted_text=cleaned,
        safety_flags=safety_flags,
        redactions=sorted(set(redactions)),
    )
