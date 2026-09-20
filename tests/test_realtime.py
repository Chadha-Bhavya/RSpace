import unittest

from realtime import SentenceChunker


class TestSentenceChunker(unittest.TestCase):
    def test_emits_complete_sentences_from_model_deltas(self):
        chunker = SentenceChunker()
        self.assertEqual(chunker.push("That sounds like a lovely "), [])
        self.assertEqual(chunker.push("morning. What happened next? "), [
            "That sounds like a lovely morning.",
            "What happened next?",
        ])
        self.assertEqual(chunker.finish(), "")

    def test_flushes_short_final_text(self):
        chunker = SentenceChunker()
        chunker.push("I understand")
        self.assertEqual(chunker.finish(), "I understand")


if __name__ == "__main__":
    unittest.main()
