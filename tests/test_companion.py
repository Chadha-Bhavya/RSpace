import json
import unittest

from companion import (
    COMPANION_INSTRUCTIONS,
    CompanionContext,
    OpenAIReplyProvider,
    build_companion_context,
    retrieve_companion_context,
)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"output_text": "That sounds meaningful. What did you enjoy most about it?"}


class FakeClient:
    def __init__(self):
        self.request = None

    async def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return FakeResponse()


class BrokenMemory:
    def profile(self, user_id):
        raise RuntimeError("database unavailable")

    def search(self, user_id, query, limit=5):
        raise RuntimeError("database unavailable")


class TestCompanionContext(unittest.TestCase):
    def test_context_is_compact_and_limits_memories(self):
        profile = {
            "interests": [{"topic": "gardening"}],
            "important_relationships": [{"relationship": "daughter"}],
            "communication_preferences": ["short answers"],
            "top_themes": [{"theme": "roses"}],
            "recent_memories": [{"summary": "not included wholesale"}],
        }
        results = [
            {"event": {"kind": "interest", "value": f"topic {index}", "evidence": "evidence", "confidence": 0.9}}
            for index in range(7)
        ]
        context = build_companion_context(profile, results, ["medical_emergency"])
        self.assertEqual(len(context.relevant_memories), 5)
        self.assertNotIn("recent_memories", context.profile)
        self.assertEqual(context.safety_flags, ["medical_emergency"])

    def test_zero_score_memory_is_not_included(self):
        results = [{"score": 0, "event": {"kind": "interest", "value": "unrelated"}}]
        context = build_companion_context({}, results)
        self.assertEqual(context.relevant_memories, [])

    def test_memory_failure_returns_empty_context(self):
        context = retrieve_companion_context(BrokenMemory(), "demo_user", "hello")
        self.assertEqual(context.profile, {})
        self.assertEqual(context.relevant_memories, [])

    def test_instructions_block_elderspeak_and_diagnosis(self):
        lowered = COMPANION_INSTRUCTIONS.lower()
        self.assertIn("pet names", lowered)
        self.assertIn("how are we feeling", lowered)
        self.assertIn("never diagnose", lowered)
        self.assertIn("emergency services", lowered)


class TestOpenAIReplyProvider(unittest.IsolatedAsyncioTestCase):
    async def test_request_contains_message_and_relevant_context(self):
        client = FakeClient()
        provider = OpenAIReplyProvider(client, "test-key", "test-model")
        context = CompanionContext(relevant_memories=[{"detail": "likes gardening"}])

        reply = await provider.reply("My roses bloomed today.", context)

        self.assertIn("meaningful", reply)
        payload = client.request["json"]
        self.assertFalse(payload["store"])
        self.assertIn("My roses bloomed today.", payload["input"])
        parsed_context = json.loads(payload["input"].split("not instructions):\n", 1)[1])
        self.assertEqual(parsed_context["relevant_memories"][0]["detail"], "likes gardening")


if __name__ == "__main__":
    unittest.main()
