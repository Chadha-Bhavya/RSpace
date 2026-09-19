"""
Extraction layer — the ONLY place OpenAI is called from.

Responsibility split:
  - OpenAI (or the mock standing in for it) handles natural-language
    understanding: pulling structured signals out of free text,
    normalizing concepts, judging strength/confidence, flagging
    ambiguity, and phrasing follow-up questions.
  - Everything downstream (validation.py, matching.py, ranking.py) is
    plain deterministic Python that never calls an LLM.

`ExtractorClient` is a Protocol, so OpenAIExtractorClient and
MockExtractorClient are interchangeable everywhere else in the codebase.
This is what makes the matching system testable without a network
connection or API key.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Protocol

from models import InterestStrength


# ----------------------------------------------------------------------
# JSON schema OpenAI is asked to return. A plain constant, not buried in
# a prompt string, so it's easy to read and adjust.
# ----------------------------------------------------------------------
EXTRACTION_JSON_SCHEMA: Dict[str, Any] = {
    "name": "senior_profile_extraction",
    "schema": {
        "type": "object",
        "properties": {
            "interests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Canonical, lowercase interest name, e.g. 'gardening'",
                        },
                        "strength": {
                            "type": "string",
                            "enum": ["frequent", "occasional", "former", "unknown"],
                        },
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source_phrase": {
                            "type": "string",
                            "description": "The exact words in the input this was extracted from",
                        },
                    },
                    "required": ["topic", "strength", "confidence", "source_phrase"],
                },
            },
            "location": {"type": ["string", "null"]},
            "languages": {"type": "array", "items": {"type": "string"}},
            "availability": {
                "type": "array",
                "items": {"type": "string", "enum": ["morning", "afternoon", "evening", "weekend"]},
            },
            "preferred_comm_mode": {
                "type": ["string", "null"],
                "enum": ["voice", "video", "text", None],
            },
            "background_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short icebreaker-worthy facts that don't fit another field",
            },
        },
        "required": [
            "interests", "location", "languages", "availability",
            "preferred_comm_mode", "background_notes",
        ],
    },
}

EXTRACTION_SYSTEM_PROMPT = """You extract structured information from a senior citizen's spoken \
answer for a social-matching app. Only extract what is clearly supported by the text — never \
invent interests, places, or preferences that were not stated or strongly implied. For every \
interest, copy the exact phrase it came from into source_phrase, so it can be checked against \
the original text. If the person's level of engagement (frequent / occasional / former) is not \
clear, use "unknown" rather than guessing. Respond ONLY with JSON matching the provided schema."""

CLARIFICATION_SYSTEM_PROMPT = """Write ONE short, warm, simple follow-up question (under 20 \
words) for a senior citizen, to clarify how often they currently do the activity mentioned. \
Return only the question, nothing else."""


class ExtractorClient(Protocol):
    """Anything that can turn raw text into the extraction JSON shape,
    and optionally phrase a clarification question, can be used here."""

    def extract(self, raw_text: str) -> Dict[str, Any]: ...

    def generate_clarification(self, topic: str, raw_text: str) -> str: ...


# ----------------------------------------------------------------------
# Real OpenAI-backed client.
# ----------------------------------------------------------------------
class OpenAIExtractorClient:
    """Talks to the OpenAI API.

    Reads OPENAI_API_KEY from the environment — never hardcode a key.
    Model name is configurable via the OPENAI_MODEL environment variable
    so it's not scattered through the codebase.

    The `openai` package is imported lazily (inside __init__) so nothing
    else in this project needs it installed to run or be tested.
    """

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, model: Optional[str] = None):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it before using OpenAIExtractorClient."
            )
        try:
            from openai import OpenAI  # lazy import — optional dependency
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is required for OpenAIExtractorClient. "
                "Install it with: pip install openai"
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self.model = model or os.environ.get("OPENAI_MODEL", self.DEFAULT_MODEL)

    def extract(self, raw_text: str) -> Dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_schema", "json_schema": EXTRACTION_JSON_SCHEMA},
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)

    def generate_clarification(self, topic: str, raw_text: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CLARIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": f'They said: "{raw_text}". Topic to clarify: {topic}.'},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()


# ----------------------------------------------------------------------
# Deterministic mock client. Stands in for OpenAI in unit tests and in
# the offline demo — same JSON shape, so everything downstream is
# exercised exactly the way it would be with the real API.
# ----------------------------------------------------------------------
_INTEREST_KEYWORDS: Dict[str, List[str]] = {
    "gardening": ["garden", "gardening"],
    "jazz": ["jazz"],
    "music": ["piano", "singing", "choir", "guitar"],
    "basketball": ["basketball"],
    "tennis": ["tennis"],
    "reading": ["read", "reading", "book club", "books"],
    "walking": ["walk", "walking", "hiking"],
    "cooking": ["cook", "cooking", "baking"],
    "cards_games": ["cards", "bridge", "chess", "bingo"],
    "travel": ["travel", "traveling", "trips"],
    "pets": ["dog", "cat", "pet", "puppy"],
    "grandchildren": ["grandkids", "grandchildren", "grandson", "granddaughter"],
}

_FREQUENT_MARKERS = ["every week", "every day", "regularly", "still love", "still play", "always"]
_OCCASIONAL_MARKERS = ["sometimes", "once in a while", "occasionally", "now and then"]
_FORMER_MARKERS = ["used to", "back when", "no longer", "haven't in a while", "miss having"]


class MockExtractorClient:
    """Deterministic stand-in for OpenAI. Deliberately simple keyword
    matching — good enough to exercise the whole pipeline in tests and
    offline demos without any network access or API key."""

    def extract(self, raw_text: str) -> Dict[str, Any]:
        norm = raw_text.lower()
        interests = []
        for topic, keywords in _INTEREST_KEYWORDS.items():
            for kw in keywords:
                if kw in norm:
                    sentence = self._sentence_containing(raw_text, kw)
                    strength = self._infer_strength(sentence.lower())
                    interests.append({
                        "topic": topic,
                        "strength": strength.value,
                        "confidence": 0.85 if strength != InterestStrength.UNKNOWN else 0.6,
                        "source_phrase": sentence,
                    })
                    break
        return {
            "interests": interests,
            "location": None,
            "languages": [],
            "availability": [],
            "preferred_comm_mode": None,
            "background_notes": [],
        }

    def generate_clarification(self, topic: str, raw_text: str) -> str:
        return f"Would you say you enjoy {topic.replace('_', ' ')} often, sometimes, or rarely these days?"

    @staticmethod
    def _infer_strength(sentence: str) -> InterestStrength:
        if any(m in sentence for m in _FORMER_MARKERS):
            return InterestStrength.FORMER
        if any(m in sentence for m in _FREQUENT_MARKERS):
            return InterestStrength.FREQUENT
        if any(m in sentence for m in _OCCASIONAL_MARKERS):
            return InterestStrength.OCCASIONAL
        return InterestStrength.UNKNOWN

    @staticmethod
    def _sentence_containing(raw_text: str, keyword: str) -> str:
        for sentence in re.split(r"(?<=[.!?])\s+", raw_text):
            if keyword in sentence.lower():
                return sentence.strip()
        return raw_text.strip()