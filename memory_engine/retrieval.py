from __future__ import annotations

import math
import re
from collections import Counter

from .embeddings import Embedder, cosine_similarity
from .models import MemoryEvent


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_scores(query: str, events: list[MemoryEvent], k1: float = 1.5, b: float = 0.75) -> list[float]:
    documents = [_tokens(f"{event.kind} {event.value} {event.evidence}") for event in events]
    if not documents:
        return []
    query_terms = set(_tokens(query))
    average_length = sum(map(len, documents)) / len(documents) or 1.0
    frequencies = Counter(term for term in query_terms for document in documents if term in set(document))
    scores: list[float] = []
    for document in documents:
        counts = Counter(document)
        score = 0.0
        for term in query_terms:
            document_frequency = frequencies[term]
            inverse_frequency = math.log(1 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5))
            frequency = counts[term]
            denominator = frequency + k1 * (1 - b + b * len(document) / average_length)
            if denominator:
                score += inverse_frequency * frequency * (k1 + 1) / denominator
        scores.append(score)
    maximum = max(scores, default=0.0)
    return [score / maximum if maximum else 0.0 for score in scores]


def hybrid_search(query: str, events: list[MemoryEvent], embedder: Embedder, limit: int = 5) -> list[dict]:
    if not events:
        return []
    query_vector = embedder.embed(query)
    lexical_scores = _bm25_scores(query, events)
    semantic_scores = [
        max(0.0, cosine_similarity(query_vector, event.embedding))
        if event.embedding_backend == embedder.name else 0.0
        for event in events
    ]
    relevance = [0.45 * lexical + 0.55 * semantic for lexical, semantic in zip(lexical_scores, semantic_scores)]

    # Maximal Marginal Relevance: prefer relevant results without returning five
    # nearly identical memories from the same repeated story.
    selected: list[int] = []
    remaining = set(range(len(events)))
    while remaining and len(selected) < limit:
        def mmr(index: int) -> float:
            diversity_penalty = max(
                (cosine_similarity(events[index].embedding, events[chosen].embedding) for chosen in selected),
                default=0.0,
            )
            return 0.72 * relevance[index] - 0.28 * diversity_penalty

        winner = max(remaining, key=mmr)
        if relevance[winner] <= 0 and selected:
            break
        selected.append(winner)
        remaining.remove(winner)

    results = []
    for index in selected:
        event = events[index].to_dict()
        event.pop("embedding", None)
        results.append({
            "event": event,
            "score": round(relevance[index], 4),
            "keyword_score": round(lexical_scores[index], 4),
            "semantic_score": round(semantic_scores[index], 4),
        })
    return results
