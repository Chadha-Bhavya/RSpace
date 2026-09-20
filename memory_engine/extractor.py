from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

from .models import MemoryDraft


class MemoryExtractor(Protocol):
    name: str

    def extract(self, redacted_text: str) -> list[MemoryDraft]: ...


EXTRACTION_INSTRUCTIONS = """You extract useful long-term memories from a conversation with an older adult.
Return only facts directly supported by the supplied redacted transcript.
Use an exact substring of the transcript as evidence for every item.
Preserve negation and whether an interest is former, occasional, frequent, or unknown.
Extract important dates such as birthdays and anniversaries when the person and date are explicit. For a
recurring date, use MM-DD. For a one-time dated plan, use YYYY-MM-DD when the year is explicit. Keep the
original date wording in value when a normalized date cannot be supported. Extract specific future plans
that would make a natural follow-up. Prefer durable interests, relationships, communication preferences,
social connection signals, important dates, plans, and meaningful personal events. Ignore greetings,
filler, assistant speech, and unsupported inference.
Never diagnose medical or mental-health conditions. One memory item should represent one claim.
"""


MEMORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memories": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": [
                        "interest", "relationship", "social_signal", "availability",
                        "communication_preference", "conversation_note", "important_date", "plan",
                    ]},
                    "value": {"type": "string", "minLength": 1, "maxLength": 200},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "polarity": {"type": ["string", "null"], "enum": ["positive", "negative", "unknown", None]},
                    "strength": {"type": ["string", "null"], "enum": [
                        "former", "occasional", "frequent", "unknown", "none", None,
                    ]},
                    "keywords": {
                        "type": "array", "items": {"type": "string", "maxLength": 50}, "maxItems": 10,
                    },
                    "person": {"type": ["string", "null"], "maxLength": 100},
                    "date": {"type": ["string", "null"], "maxLength": 10},
                    "occasion": {"type": ["string", "null"], "maxLength": 80},
                },
                "required": [
                    "kind", "value", "confidence", "evidence", "polarity", "strength", "keywords",
                    "person", "date", "occasion",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["memories"],
    "additionalProperties": False,
}


def drafts_from_payload(payload: dict[str, Any]) -> list[MemoryDraft]:
    drafts: list[MemoryDraft] = []
    for item in payload.get("memories", []):
        if not isinstance(item, dict):
            continue
        attributes: dict[str, Any] = {}
        if item.get("polarity") is not None:
            attributes["polarity"] = item["polarity"]
        if item.get("strength") is not None:
            attributes["strength"] = item["strength"]
        if item.get("keywords"):
            attributes["keywords"] = [str(value) for value in item["keywords"]]
        for key in ("person", "date", "occasion"):
            if item.get(key) is not None:
                attributes[key] = str(item[key]).strip()
        try:
            drafts.append(MemoryDraft(
                kind=str(item["kind"]),
                value=str(item["value"]).strip(),
                confidence=float(item["confidence"]),
                evidence=str(item["evidence"]),
                attributes=attributes,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return drafts


def _output_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"]).strip()
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


class OpenAIMemoryExtractor:
    name = "openai-structured-v1"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def extract(self, redacted_text: str) -> list[MemoryDraft]:
        if not redacted_text.strip():
            return []
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "instructions": EXTRACTION_INSTRUCTIONS,
                    "input": redacted_text,
                    "reasoning": {"effort": "minimal"},
                    "text": {"format": {
                        "type": "json_schema", "name": "memory_extraction",
                        "strict": True, "schema": MEMORY_SCHEMA,
                    }},
                    "max_output_tokens": 1500,
                    "store": False,
                },
            )
            response.raise_for_status()
        text = _output_text(response.json())
        if not text:
            return []
        try:
            return drafts_from_payload(json.loads(text))
        except json.JSONDecodeError as error:
            raise RuntimeError("The AI memory parser returned invalid structured data.") from error


def create_extractor() -> MemoryExtractor:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        raise RuntimeError("OPENAI_API_KEY is required for AI memory extraction.")
    model = os.getenv("OPENAI_MEMORY_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    return OpenAIMemoryExtractor(api_key, model)
