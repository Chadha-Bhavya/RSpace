"""
End-to-end demo: raw statement -> extraction -> profile -> match ->
explanation.

Uses MockExtractorClient so this runs immediately with no API key or
network access. To use real OpenAI extraction instead, change the one
line marked below to:

    client = OpenAIExtractorClient()   # requires OPENAI_API_KEY to be set

Nothing else in this file (or in matching.py / ranking.py) needs to
change — that's the point of the ExtractorClient seam.
"""

from dotenv import load_dotenv

load_dotenv()  # no-op if you're only using MockExtractorClient below; picks up
                # OPENAI_API_KEY / OPENAI_MODEL from .env automatically if you
                # switch to OpenAIExtractorClient.

from extraction import MockExtractorClient
from matching import compute_match
from models import UserProfile
from ranking import find_matches
from validation import apply_extraction


def build_profile(user_id: str, statements, client) -> UserProfile:
    profile = UserProfile(user_id=user_id)
    for statement in statements:
        print(f"  raw statement: {statement!r}")
        extraction = client.extract(statement)
        print(f"  extracted:     {extraction}")
        clarifications = apply_extraction(profile, statement, extraction, client)
        if clarifications:
            print(f"  -> follow-up:  {clarifications}")
    return profile


def main():
    client = MockExtractorClient()  # swap for OpenAIExtractorClient() to use the real API

    print("=== Building profile: Eleanor ===")
    eleanor = build_profile("eleanor", [
        "I used to garden with my husband, and I really miss having someone to "
        "talk to about gardening. I also love old jazz and watching basketball.",
    ], client)
    print("Final profile:", eleanor.to_dict())
    print()

    print("=== Building profile: Walter ===")
    walter = build_profile("walter", [
        "I still garden every week, it's my favorite thing. I love jazz too, "
        "and I play tennis sometimes.",
    ], client)
    print("Final profile:", walter.to_dict())
    print()

    print("=== Building profile: Ruth (no overlap) ===")
    ruth = build_profile("ruth", [
        "I mostly enjoy reading books and playing bridge with my friends.",
    ], client)
    print("Final profile:", ruth.to_dict())
    print()

    print("=== Match: Eleanor vs Walter ===")
    result = compute_match(eleanor, walter)
    print(f"{int(result.score * 100)}% match")
    print("Shared interests:", result.shared_interests)
    print("Explanation:", result.explanation)
    print()

    print("=== Ranking candidates for Eleanor ===")
    ranked = find_matches(eleanor, [walter, ruth])
    for r in ranked:
        print(f"  {r.other_user_id}: {r.score} \u2014 {r.explanation}")


if __name__ == "__main__":
    main()