from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

from .models import MemoryEvent


INDEX_NAME = "rspace-memories"
EMBEDDING_DIMENSIONS = 384


class HttpClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any): ...


class ElasticsearchMemoryIndex:
    """Best-effort secondary index. PostgreSQL remains the source of truth."""

    def __init__(self, url: str, api_key: str, client: HttpClient | None = None) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key.removeprefix("ApiKey ").strip()
        self.client = client or httpx.Client()
        self._initialized = False

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"ApiKey {self.api_key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs: Any):
        response = self.client.request(
            method, f"{self.url}/{path.lstrip('/')}", headers=self.headers, timeout=8.0, **kwargs
        )
        return response

    def ensure_index(self) -> None:
        if self._initialized:
            return
        response = self._request("HEAD", INDEX_NAME)
        if response.status_code == 404:
            response = self._request("PUT", INDEX_NAME, json={
                "mappings": {
                    "dynamic": "strict",
                    "properties": {
                        "user_id": {"type": "keyword"},
                        "memory_id": {"type": "keyword"},
                        "text": {"type": "text"},
                        "category": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": EMBEDDING_DIMENSIONS,
                            "index": True,
                            "similarity": "cosine",
                        },
                    },
                }
            })
            # A concurrent request may have created the index first.
            if response.status_code not in {200, 201, 400}:
                response.raise_for_status()
        elif response.status_code >= 400:
            response.raise_for_status()
        self._initialized = True

    def index_events(self, events: list[MemoryEvent]) -> None:
        if not events:
            return
        self.ensure_index()
        for event in events:
            if len(event.embedding) != EMBEDDING_DIMENSIONS:
                raise ValueError("Elasticsearch memories require 384-dimensional embeddings.")
            text = event.value.strip()
            if event.evidence.strip() and event.evidence.strip() != text:
                text = f"{text}. {event.evidence.strip()}"
            response = self._request("PUT", f"{INDEX_NAME}/_doc/{event.event_id}", json={
                "user_id": event.user_id,
                "memory_id": event.event_id,
                "text": text,
                "category": event.kind,
                "created_at": event.timestamp,
                "embedding": event.embedding,
            })
            response.raise_for_status()

    def search(
        self,
        user_id: str,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        if len(query_vector) != EMBEDDING_DIMENSIONS:
            raise ValueError("Elasticsearch queries require 384-dimensional embeddings.")
        filters: list[dict[str, Any]] = [{"term": {"user_id": user_id}}]
        if category:
            filters.append({"term": {"category": category}})
        if date_from or date_to:
            bounds = {key: value for key, value in (("gte", date_from), ("lte", date_to)) if value}
            filters.append({"range": {"created_at": bounds}})

        candidates = max(20, limit * 5)
        payload = {
            "size": limit,
            "_source": ["user_id", "memory_id", "text", "category", "created_at"],
            "query": {
                "bool": {
                    "filter": filters,
                    "minimum_should_match": 1,
                    "should": [
                        {"match": {"text": {"query": query, "boost": 1.0}}},
                        {"knn": {
                            "field": "embedding",
                            "query_vector": query_vector,
                            "k": candidates,
                            "num_candidates": max(100, candidates),
                            "boost": 2.0,
                            "filter": filters,
                        }},
                    ],
                }
            },
        }
        response = self._request("POST", f"{INDEX_NAME}/_search", json=payload)
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            source = hit.get("_source") or {}
            # Defense in depth in case an upstream proxy or test double ignores filters.
            if source.get("user_id") != user_id:
                continue
            text = str(source.get("text") or "")
            results.append({
                "event": {
                    "event_id": source.get("memory_id"),
                    "user_id": source.get("user_id"),
                    "timestamp": source.get("created_at"),
                    "kind": source.get("category"),
                    "value": text,
                    "evidence": text,
                },
                "score": float(hit.get("_score") or 0.0),
                "retrieval_backend": "elasticsearch",
            })
        return results


def create_elasticsearch_index() -> ElasticsearchMemoryIndex | None:
    url = os.getenv("ELASTICSEARCH_URL", "").strip()
    api_key = os.getenv("ELASTIC_API_KEY", "").strip()
    if not url or not api_key:
        return None
    return ElasticsearchMemoryIndex(url, api_key)
