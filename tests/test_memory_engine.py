import json
import tempfile
import unittest
from pathlib import Path

from memory_engine.embeddings import HashingEmbedder
from memory_engine.engine import MemoryEngine
from memory_engine.extractor import drafts_from_payload
from memory_engine.filters import filter_text
from memory_engine.models import MemoryDraft
from memory_engine.validation import validate_drafts


class StubAIExtractor:
    name = "stub-ai"

    def extract(self, text):
        lower = text.lower()
        drafts = []
        if "gardening" in lower or "growing flowers" in lower:
            drafts.append(MemoryDraft("interest", "gardening", 0.9, text, {"polarity": "positive"}))
        if "lonely" in lower:
            drafts.append(MemoryDraft("social_signal", "loneliness", 0.9, text, {"polarity": "positive"}))
        if "daughter called" in lower:
            drafts.append(MemoryDraft("social_signal", "social_connection", 0.8, text, {"polarity": "positive"}))
        if "radio" in lower:
            drafts.append(MemoryDraft(
                "conversation_note", "repaired father's radio", 0.8, text,
                {"keywords": ["repaired", "radio", "father"]},
            ))
        return drafts


class TestMemoryPipeline(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(
            Path(self.temporary_directory.name),
            embedder=HashingEmbedder(),
            extractor=StubAIExtractor(),
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_pii_is_redacted_and_safety_is_flagged(self):
        result = filter_text("Call me at 617-555-1212. I don't want to live.")
        self.assertNotIn("617-555-1212", result.redacted_text)
        self.assertIn("phone", result.redactions)
        self.assertIn("self_harm", result.safety_flags)

    def test_negation_is_preserved(self):
        text = "I am not lonely today. I do not enjoy gardening anymore."
        drafts = validate_drafts(text, drafts_from_payload({"memories": [
            {"kind": "social_signal", "value": "loneliness", "confidence": 0.9,
             "evidence": "I am not lonely today.", "polarity": "negative", "strength": None, "keywords": []},
            {"kind": "interest", "value": "gardening", "confidence": 0.9,
             "evidence": "I do not enjoy gardening anymore.", "polarity": "negative", "strength": "none", "keywords": []},
        ]}))
        loneliness = next(draft for draft in drafts if draft.value == "loneliness")
        gardening = next(draft for draft in drafts if draft.value == "gardening")
        self.assertEqual(loneliness.attributes["polarity"], "negative")
        self.assertEqual(gardening.attributes["polarity"], "negative")

    def test_temporal_interest_strength(self):
        text = "I used to garden with my husband."
        drafts = validate_drafts(text, drafts_from_payload({"memories": [{
            "kind": "interest", "value": "gardening", "confidence": 0.9,
            "evidence": text, "polarity": "positive", "strength": "former", "keywords": [],
        }]}))
        gardening = next(draft for draft in drafts if draft.kind == "interest")
        self.assertEqual(gardening.attributes["strength"], "former")
        self.assertEqual(gardening.evidence, text)

    def test_meaningful_uncategorized_sentence_is_saved(self):
        result = self.engine.process(
            "alice",
            "Yesterday I repaired an old radio that belonged to my father.",
        )
        self.assertTrue(any(item["kind"] == "conversation_note" for item in result["stored_memories"]))
        profile = self.engine.profile("alice")
        self.assertTrue(profile["recent_memories"])

    def test_process_stores_jsonl_without_raw_pii(self):
        result = self.engine.process(
            "alice",
            "I love gardening and my daughter called me. Reach me at alice@example.com.",
        )
        self.assertGreater(result["stored_count"], 0)
        event_path = Path(self.temporary_directory.name) / "alice" / "events.jsonl"
        stored_text = event_path.read_text(encoding="utf-8")
        self.assertNotIn("alice@example.com", stored_text)
        for line in stored_text.splitlines():
            json.loads(line)

    def test_recent_exact_duplicates_are_not_stored_twice(self):
        first = self.engine.process("alice", "I enjoy gardening every week.")
        second = self.engine.process("alice", "I enjoy gardening every week.")
        self.assertGreater(first["stored_count"], 0)
        self.assertEqual(second["stored_count"], 0)
        self.assertGreater(second["duplicate_count"], 0)

    def test_hybrid_search_finds_related_concept(self):
        self.engine.process("alice", "I enjoy gardening and growing flowers.")
        results = self.engine.search("alice", "working with plants")
        self.assertTrue(results)
        self.assertEqual(results[0]["event"]["value"], "gardening")
        self.assertGreater(results[0]["semantic_score"], 0)
        self.assertNotIn("embedding", results[0]["event"])

    def test_profile_and_report_are_non_diagnostic(self):
        self.engine.process("alice", "I feel lonely today, but my daughter called me.")
        profile = self.engine.profile("alice")
        report = self.engine.report("alice")
        self.assertGreater(profile["event_count"], 0)
        self.assertEqual(report["data_quality"], "insufficient_data")
        self.assertIn("does not diagnose", report["disclaimer"])


if __name__ == "__main__":
    unittest.main()
