import json
import unittest
from datetime import datetime, timezone

from companion import (
    COMPANION_INSTRUCTIONS,
    CompanionContext,
    OpenAIReplyProvider,
    build_companion_context,
    build_timeline_context,
    detect_end_conversation,
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


class FakeStreamResponse:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        yield 'event: response.output_text.delta'
        yield 'data: {"type":"response.output_text.delta","delta":"That sounds "}'
        yield 'data: {"type":"response.output_text.delta","delta":"meaningful."}'
        yield 'data: [DONE]'


class FakeStreamingClient(FakeClient):
    def stream(self, method, url, **kwargs):
        self.request = {"method": method, "url": url, **kwargs}
        return FakeStreamResponse()


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
            "event_count": 22,
            "recent_memories": [
                {"summary": "Planted roses", "timestamp": "2026-09-18", "confidence": 0.9},
                {"summary": "Plans to call Sam", "timestamp": "2026-09-17", "confidence": 0.8},
                {"summary": "not included", "timestamp": "2026-09-16", "confidence": 0.7},
            ],
        }
        results = [
            {"event": {"kind": "interest", "value": f"topic {index}", "evidence": "evidence", "confidence": 0.9}}
            for index in range(7)
        ]
        context = build_companion_context(profile, results, ["medical_emergency"])
        self.assertEqual(len(context.relevant_memories), 6)
        self.assertNotIn("recent_memories", context.profile)
        self.assertEqual(len(context.recent_continuity), 2)
        self.assertEqual(context.familiarity, "established")
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
        self.assertIn("unfinished plan", lowered)
        self.assertIn("supplied timing context", lowered)
        self.assertIn("expresses loneliness", lowered)

    def test_timeline_describes_long_gap_and_finds_todays_event(self):
        profile = {
            "important_dates": [{
                "person": "Maya", "occasion": "birthday", "date": "09-20", "value": "Maya's birthday",
            }],
        }
        timeline = build_timeline_context(
            profile,
            {
                "current_session": {
                    "started_at": "2026-09-20T14:00:00+00:00", "timezone": "UTC",
                },
                "previous_session": {"ended_at": "2026-09-13T14:00:00+00:00"},
            },
            True,
            now=datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(timeline["time_since_previous_conversation"], "about one week")
        self.assertTrue(timeline["first_turn_in_session"])
        self.assertEqual(timeline["important_events_today"][0]["person"], "Maya")

    def test_end_conversation_intent_is_detected_without_false_negation(self):
        self.assertTrue(detect_end_conversation("Please end the conversation with me right now."))
        self.assertTrue(detect_end_conversation("That's all for now, bye."))
        self.assertTrue(detect_end_conversation("Leave me alone."))
        self.assertFalse(detect_end_conversation("I don't want to stop talking."))
        self.assertFalse(detect_end_conversation("Don't end the conversation."))


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

    async def test_stream_reply_yields_text_before_completion(self):
        client = FakeStreamingClient()
        provider = OpenAIReplyProvider(client, "test-key", "test-model")

        parts = [part async for part in provider.stream_reply("Hello", CompanionContext())]

        self.assertEqual(parts, ["That sounds ", "meaningful."])
        self.assertTrue(client.request["json"]["stream"])
        self.assertEqual(client.request["json"]["max_output_tokens"], 180)
        self.assertEqual(client.request["json"]["reasoning"]["effort"], "low")


if __name__ == "__main__":
    unittest.main()
