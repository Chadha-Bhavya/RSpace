"""
Unit tests for the matching system. Run with:

    cd senior_match && python3 -m unittest tests.py -v

Uses MockExtractorClient throughout — no network access or API key
needed to run these.
"""

import unittest

from extraction import MockExtractorClient
from matching import compute_match
from models import CommMode, ExtractedInterest, FieldValue, InterestStrength, TimeBlock, UserProfile
from ranking import find_matches
from validation import apply_extraction


def make_profile(uid, interests=None, location=None, languages=None,
                  availability=None, comm_mode=None) -> UserProfile:
    """Test helper: builds a profile directly from structured data,
    bypassing extraction, so matching logic can be tested in isolation."""
    p = UserProfile(user_id=uid)
    for topic, strength, confidence in (interests or []):
        p.upsert_interest(ExtractedInterest(topic=topic, strength=strength,
                                             confidence=confidence, source_phrase=topic))
    if location:
        p.location = FieldValue(value=location, confidence=0.9)
    if languages:
        p.languages = set(languages)
    if availability:
        p.availability = set(availability)
    p.preferred_comm_mode = comm_mode
    return p


class TestMatching(unittest.TestCase):

    def test_strong_match(self):
        a = make_profile(
            "a",
            interests=[("gardening", InterestStrength.FREQUENT, 0.9),
                       ("jazz", InterestStrength.FREQUENT, 0.9)],
            location="Riverdale", languages=["english"],
            availability={TimeBlock.MORNING}, comm_mode=CommMode.VOICE,
        )
        b = make_profile(
            "b",
            interests=[("gardening", InterestStrength.FREQUENT, 0.9),
                       ("jazz", InterestStrength.OCCASIONAL, 0.8)],
            location="Riverdale", languages=["english"],
            availability={TimeBlock.MORNING}, comm_mode=CommMode.VOICE,
        )
        result = compute_match(a, b)
        self.assertGreater(result.score, 0.7)
        self.assertIn("gardening", result.shared_interests)

    def test_weak_match(self):
        a = make_profile("a", interests=[("gardening", InterestStrength.FORMER, 0.6)], location="Riverdale")
        b = make_profile("b", interests=[("basketball", InterestStrength.FREQUENT, 0.9)], location="Elmwood")
        result = compute_match(a, b)
        self.assertLess(result.score, 0.3)

    def test_partial_information_excludes_uncomparable_dimensions(self):
        a = make_profile("a", interests=[("gardening", InterestStrength.FREQUENT, 0.9)])
        b = make_profile("b", interests=[("gardening", InterestStrength.FREQUENT, 0.9)], location="Riverdale")
        result = compute_match(a, b)
        # `a` has no location, so location can't be compared at all —
        # it should be excluded from the breakdown entirely, not scored as 0.
        self.assertNotIn("location", result.breakdown)
        self.assertIn("interests", result.breakdown)

    def test_missing_information_does_not_zero_out_score(self):
        a = make_profile("a", interests=[("gardening", InterestStrength.FREQUENT, 0.9)])
        b = make_profile("b", interests=[("gardening", InterestStrength.FREQUENT, 0.9)])
        result = compute_match(a, b)
        self.assertGreater(result.score, 0.0)

    def test_no_meaningful_overlap(self):
        a = make_profile("a", interests=[("gardening", InterestStrength.FREQUENT, 0.9)])
        b = make_profile("b", interests=[("basketball", InterestStrength.FREQUENT, 0.9)])
        result = compute_match(a, b)
        self.assertEqual(result.shared_interests, [])
        self.assertEqual(result.breakdown["interests"], 0.0)

    def test_ambiguous_information_triggers_clarification(self):
        profile = UserProfile(user_id="c")
        client = MockExtractorClient()
        raw_text = "I play tennis sometimes but I'm not always sure."
        extraction = {
            "interests": [{
                "topic": "tennis", "strength": "unknown", "confidence": 0.5,
                "source_phrase": "I play tennis sometimes",
            }],
            "location": None, "languages": [], "availability": [],
            "preferred_comm_mode": None, "background_notes": [],
        }
        clarifications = apply_extraction(profile, raw_text, extraction, client)
        self.assertTrue(len(clarifications) > 0)
        self.assertIn("tennis", profile.interests)

    def test_low_confidence_below_floor_is_not_stored(self):
        profile = UserProfile(user_id="e")
        client = MockExtractorClient()
        raw_text = "I might have mentioned chess once, not sure it counts."
        extraction = {
            "interests": [{
                "topic": "chess", "strength": "unknown", "confidence": 0.1,
                "source_phrase": "chess",
            }],
            "location": None, "languages": [], "availability": [],
            "preferred_comm_mode": None, "background_notes": [],
        }
        apply_extraction(profile, raw_text, extraction, client)
        self.assertNotIn("chess", profile.interests)

    def test_hallucinated_interest_is_dropped(self):
        """The extractor claims a source_phrase that never appeared in
        what the user actually said — validation should refuse to store
        it, regardless of how confident the model claims to be."""
        profile = UserProfile(user_id="d")
        client = MockExtractorClient()
        raw_text = "I like gardening."
        fake_extraction = {
            "interests": [{
                "topic": "skydiving", "strength": "frequent", "confidence": 0.95,
                "source_phrase": "I go skydiving every weekend",
            }],
            "location": None, "languages": [], "availability": [],
            "preferred_comm_mode": None, "background_notes": [],
        }
        apply_extraction(profile, raw_text, fake_extraction, client)
        self.assertNotIn("skydiving", profile.interests)

    def test_ranking_multiple_candidates(self):
        user = make_profile(
            "user",
            interests=[("gardening", InterestStrength.FREQUENT, 0.9),
                       ("jazz", InterestStrength.FREQUENT, 0.9)],
            location="Riverdale",
        )
        strong = make_profile(
            "strong",
            interests=[("gardening", InterestStrength.FREQUENT, 0.9),
                       ("jazz", InterestStrength.FREQUENT, 0.9)],
            location="Riverdale",
        )
        medium = make_profile(
            "medium",
            interests=[("gardening", InterestStrength.OCCASIONAL, 0.7)],
            location="Elmwood",
        )
        weak = make_profile("weak", interests=[("basketball", InterestStrength.FREQUENT, 0.9)])

        ranked = find_matches(user, [strong, medium, weak], top_n=3)
        ids = [r.other_user_id for r in ranked]
        self.assertEqual(ids[0], "strong")
        self.assertGreater(ranked[0].score, ranked[1].score)


if __name__ == "__main__":
    unittest.main()