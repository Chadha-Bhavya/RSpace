import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from matching import (
    EMBEDDING_DIMENSIONS,
    JsonMatchingRepository,
    MatchingEngine,
    OpenAIInterestEmbeddingProvider,
)
from memory_engine.embeddings import HashingEmbedder


class FakeMemoryStore:
    def __init__(self, accounts):
        self.accounts = {item["user_id"]: item for item in accounts}

    def list_account_profiles(self):
        return list(self.accounts.values())

    def load_account_profile(self, user_id):
        return dict(self.accounts.get(user_id, {}))


class FakeMemory:
    def __init__(self, accounts, profiles):
        self.store = FakeMemoryStore(accounts)
        self.profiles = profiles

    def profile(self, user_id):
        return self.profiles[user_id]


class FakeSemanticEmbedder:
    name = "fake-semantic-v1"

    def embed_many(self, values):
        vectors = {}
        for value in values:
            text = value.lower()
            if "basketball" in text:
                index = 0
            elif "football" in text or "soccer" in text:
                index = 1
            elif "garden" in text:
                index = 2
            elif "jazz" in text:
                index = 3
            elif "chess" in text:
                index = 4
            elif "tennis" in text:
                index = 5
            elif "fast paced" in text:
                index = 6
            else:
                index = 7
            vector = [0.0] * EMBEDDING_DIMENSIONS
            vector[index] = 1.0
            vectors[value] = vector
        return vectors


class FakeEmbeddingResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": [
                {"index": 0, "embedding": [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)},
                {"index": 1, "embedding": [0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 2)},
            ]
        }


def profile(*interests, communication=None):
    return {
        "interests": [
            {"topic": item, "current_polarity": "positive", "evidence": "private quote"}
            for item in interests
        ],
        "communication_preferences": communication or [],
        "availability": ["Tuesday morning"],
        "social_wellness": {"loneliness_mentions": 10},
        "recent_memories": [{"evidence": "private transcript"}],
        "important_relationships": [{"relationship": "daughter"}],
    }


class TestMatchingEngine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        accounts = [
            {"user_id": "a", "display_name": "Alice", "email": "alice@example.com"},
            {"user_id": "b", "display_name": "Bob", "email": "bob@example.com"},
            {"user_id": "c", "display_name": "Carol", "email": "carol@example.com"},
        ]
        profiles = {
            "a": profile("gardening", "jazz", "diabetes support", "loneliness", communication=["short replies"]),
            "b": profile("gardening", "jazz", communication=["gentle replies"]),
            "c": profile("chess", "cooking"),
        }
        self.memory = FakeMemory(accounts, profiles)
        self.repository = JsonMatchingRepository(Path(self.temp.name))
        self.engine = MatchingEngine(
            self.memory, self.repository, HashingEmbedder(), FakeSemanticEmbedder()
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_safe_profile_excludes_private_and_wellness_data(self):
        self.engine.refresh_profiles()
        saved = self.repository.list_profiles()[0].to_dict()
        serialized = str(saved)
        self.assertNotIn("private quote", serialized)
        self.assertNotIn("private transcript", serialized)
        self.assertNotIn("loneliness", serialized)
        self.assertNotIn("Tuesday", serialized)
        self.assertNotIn("daughter", serialized)
        self.assertNotIn("diabetes", serialized)

    @patch("matching.httpx.post", return_value=FakeEmbeddingResponse())
    def test_openai_embedding_provider_batches_384_dimension_vectors(self, post):
        provider = OpenAIInterestEmbeddingProvider("test-key")

        result = provider.embed_many(["watching basketball", "playing basketball"])

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "text-embedding-3-small")
        self.assertEqual(payload["dimensions"], 384)
        self.assertEqual(payload["input"], ["watching basketball", "playing basketball"])
        self.assertEqual(len(result["watching basketball"]), 384)

    def test_cold_start_requires_two_shared_interests_and_no_self_match(self):
        matches = self.engine.find_matches("a")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Bob")
        self.assertEqual(matches[0]["shared_interests"], ["jazz", "gardening"])
        self.assertGreaterEqual(matches[0]["score"], 72)
        self.assertNotIn("email", matches[0])
        self.assertEqual(matches[0]["why"], "You both mentioned jazz and gardening.")

    def test_semantically_matches_real_world_interest_phrasing(self):
        accounts = [
            {"user_id": "x", "display_name": "X", "email": "x@example.com"},
            {"user_id": "y", "display_name": "Y", "email": "y@example.com"},
        ]
        profiles = {
            "x": profile("watching basketball", "watching football", "lawn tennis"),
            "y": profile("basketball", "playing football, soccer", "fast paced activities"),
        }
        repository = JsonMatchingRepository(Path(self.temp.name) / "phrasing")
        engine = MatchingEngine(
            FakeMemory(accounts, profiles), repository, HashingEmbedder(), FakeSemanticEmbedder()
        )

        matches = engine.find_matches("x")

        self.assertEqual(len(matches), 1)
        self.assertEqual(
            set(matches[0]["shared_interests"]), {"watching basketball", "watching football"}
        )
        self.assertGreaterEqual(matches[0]["score"], 72)

    def test_email_is_revealed_only_after_both_accept(self):
        match = self.engine.find_matches("a")[0]
        self.engine.decide("a", match["match_id"], "accept")
        self.assertEqual(self.engine.connections("a"), [])
        self.assertNotIn("email", self.engine.find_matches("a")[0])

        self.engine.decide("b", match["match_id"], "accept")
        connections = self.engine.connections("a")
        self.assertEqual(connections[0]["email"], "bob@example.com")

    def test_pass_block_and_disconnect_remove_access(self):
        match = self.engine.find_matches("a")[0]
        self.engine.decide("a", match["match_id"], "pass")
        self.assertEqual(self.engine.find_matches("a"), [])

        # A fresh repository verifies mutual acceptance, disconnection, and blocking.
        second_repository = JsonMatchingRepository(Path(self.temp.name) / "second")
        engine = MatchingEngine(
            self.memory, second_repository, HashingEmbedder(), FakeSemanticEmbedder()
        )
        match = engine.find_matches("a")[0]
        engine.decide("a", match["match_id"], "accept")
        engine.decide("b", match["match_id"], "accept")
        engine.disconnect("a", match["match_id"])
        self.assertEqual(engine.connections("a"), [])

        third_repository = JsonMatchingRepository(Path(self.temp.name) / "third")
        engine = MatchingEngine(
            self.memory, third_repository, HashingEmbedder(), FakeSemanticEmbedder()
        )
        match = engine.find_matches("a")[0]
        engine.decide("a", match["match_id"], "block")
        self.assertEqual(engine.find_matches("a"), [])
        self.assertEqual(engine.find_matches("b"), [])

    def test_ranker_learns_after_decisions(self):
        match = self.engine.find_matches("a")[0]
        for index in range(5):
            self.engine._train("a", self.repository.get_match(match["match_id"])["features"]["a"], float(index % 2 == 0))
        model = self.repository.get_model("a")
        self.assertEqual(model["decision_count"], 5)
        self.assertEqual(len(model["weights"]), 4)


if __name__ == "__main__":
    unittest.main()
