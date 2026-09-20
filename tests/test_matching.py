import tempfile
import unittest
from pathlib import Path

from matching import JsonMatchingRepository, MatchingEngine
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
        self.engine = MatchingEngine(self.memory, self.repository, HashingEmbedder())

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
        self.assertNotIn("loneliness", serialized)

    def test_cold_start_requires_two_shared_interests_and_no_self_match(self):
        matches = self.engine.find_matches("a")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Bob")
        self.assertEqual(matches[0]["shared_interests"], ["jazz", "gardening"])
        self.assertGreaterEqual(matches[0]["score"], 72)
        self.assertNotIn("email", matches[0])

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
        engine = MatchingEngine(self.memory, second_repository, HashingEmbedder())
        match = engine.find_matches("a")[0]
        engine.decide("a", match["match_id"], "accept")
        engine.decide("b", match["match_id"], "accept")
        engine.disconnect("a", match["match_id"])
        self.assertEqual(engine.connections("a"), [])

        third_repository = JsonMatchingRepository(Path(self.temp.name) / "third")
        engine = MatchingEngine(self.memory, third_repository, HashingEmbedder())
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
