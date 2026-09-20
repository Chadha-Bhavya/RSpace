from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...


CONCEPT_ALIASES = {
    "flowers": "gardening", "plants": "gardening", "garden": "gardening",
    "books": "reading", "novels": "reading", "read": "reading",
    "walks": "walking", "hike": "walking", "hiking": "walking",
    "alone": "lonely", "isolated": "lonely", "isolation": "lonely",
    "grandkids": "grandchildren", "grandson": "grandchildren", "granddaughter": "grandchildren",
    "piano": "music", "guitar": "music", "singing": "music",
}


class HashingEmbedder:
    """Deterministic local fallback using hashed unigram/bigram features.

    It is less semantic than a transformer, but private, dependency-free,
    stable across restarts, and still produces useful vectors for hybrid search.
    """

    name = "local-hashing-v1"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        tokens = [CONCEPT_ALIASES.get(token, token) for token in re.findall(r"[a-z0-9]+", text.lower())]
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            vector[index] += -1.0 if digest[0] & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbedder:
    """Optional fully local semantic embeddings.

    Install requirements-local-embeddings.txt and set
    RSPACE_EMBEDDING_BACKEND=sentence-transformers. The model is downloaded
    once, then inference stays on the machine; transcripts are not sent out.
    """

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.name = f"sentence-transformers:{model_name}"

    def embed(self, text: str) -> list[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


def create_embedder() -> Embedder:
    backend = os.getenv("RSPACE_EMBEDDING_BACKEND", "hashing").lower()
    if backend == "sentence-transformers":
        model = os.getenv("RSPACE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            return SentenceTransformerEmbedder(model)
        except (ImportError, OSError):
            # Keep the voice experience available if the optional model is not installed yet.
            return HashingEmbedder()
    return HashingEmbedder()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b))
