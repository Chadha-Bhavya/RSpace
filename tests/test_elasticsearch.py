import tempfile
import unittest
from pathlib import Path

from memory_engine.elastic import EMBEDDING_DIMENSIONS, ElasticsearchMemoryIndex
from memory_engine.embeddings import HashingEmbedder
from memory_engine.engine import MemoryEngine
from memory_engine.models import MemoryEvent
from tests.test_memory_engine import StubAIExtractor


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def event(user_id="alice"):
    return MemoryEvent(
        event_id="memory-1", user_id=user_id, timestamp="2026-09-20T10:00:00+00:00",
        kind="interest", value="gardening", confidence=0.9,
        evidence="I enjoy growing roses.", embedding=[0.1] * EMBEDDING_DIMENSIONS,
        embedding_backend="test",
    )


class TestElasticsearchMemoryIndex(unittest.TestCase):
    def test_indexes_approved_memory_and_creates_384_dimension_mapping(self):
        client = FakeClient([FakeResponse(404), FakeResponse(200), FakeResponse(201)])
        index = ElasticsearchMemoryIndex("https://elastic.example", "secret", client)

        index.index_events([event()])

        mapping = client.requests[1]["json"]["mappings"]["properties"]
        document = client.requests[2]["json"]
        self.assertEqual(mapping["embedding"]["dims"], 384)
        self.assertEqual(document["user_id"], "alice")
        self.assertEqual(document["memory_id"], "memory-1")
        self.assertEqual(len(document["embedding"]), 384)
        self.assertEqual(client.requests[2]["headers"]["Authorization"], "ApiKey secret")

    def test_hybrid_search_always_filters_user_and_supports_optional_filters(self):
        client = FakeClient([FakeResponse(200, {"hits": {"hits": [
            {"_score": 2.4, "_source": {
                "user_id": "alice", "memory_id": "a1", "text": "Enjoys roses",
                "category": "interest", "created_at": "2026-09-20T10:00:00Z",
            }},
            {"_score": 9.0, "_source": {
                "user_id": "bob", "memory_id": "b1", "text": "Private memory",
                "category": "interest", "created_at": "2026-09-20T10:00:00Z",
            }},
        ]}})])
        index = ElasticsearchMemoryIndex("https://elastic.example", "secret", client)

        results = index.search(
            "alice", "flowers", [0.1] * 384, category="interest",
            date_from="2026-09-01", date_to="2026-09-30",
        )

        payload = client.requests[0]["json"]
        filters = payload["query"]["bool"]["filter"]
        knn_filters = payload["query"]["bool"]["should"][1]["knn"]["filter"]
        self.assertIn({"term": {"user_id": "alice"}}, filters)
        self.assertEqual(filters, knn_filters)
        self.assertEqual([item["event"]["user_id"] for item in results], ["alice"])
        self.assertEqual(results[0]["retrieval_backend"], "elasticsearch")

    def test_engine_uses_elastic_results_and_falls_back_when_unavailable(self):
        class ElasticStub:
            def __init__(self):
                self.fail = False

            def index_events(self, events):
                return None

            def search(self, user_id, query, vector, limit, category, date_from, date_to):
                if self.fail:
                    raise RuntimeError("Elastic unavailable")
                return [{
                    "event": {"user_id": user_id, "kind": "interest", "value": "elastic result"},
                    "score": 1.0, "retrieval_backend": "elasticsearch",
                }]

        with tempfile.TemporaryDirectory() as directory:
            elastic = ElasticStub()
            engine = MemoryEngine(
                Path(directory), embedder=HashingEmbedder(), extractor=StubAIExtractor(),
                elastic_index=elastic,
            )
            engine.process("alice", "I enjoy gardening and growing flowers.")
            self.assertEqual(engine.search("alice", "plants")[0]["retrieval_backend"], "elasticsearch")

            elastic.fail = True
            fallback = engine.search("alice", "plants")
            self.assertEqual(fallback[0]["event"]["value"], "gardening")
            self.assertNotIn("retrieval_backend", fallback[0])


if __name__ == "__main__":
    unittest.main()
