"""
Live verification of OpenAIExtractorClient against the real API.

This is deliberately separate from demo.py (which uses the mock) and from
tests.py (which never touches the network) — this script is the only
place that actually proves the OpenAI integration works.

Usage:
    1. Copy .env.example to .env and fill in your real key.
    2. pip install -r requirements.txt
    3. python3 verify_openai_live.py

If this prints real extracted interests with sensible strength/confidence
values for the sample sentence below, your OpenAI integration is
functional. If it errors, the traceback will point at exactly what's
wrong (missing key, bad model name, network issue, schema issue, etc.).
"""

import json
import sys

from dotenv import load_dotenv

load_dotenv()  # reads .env into the environment, if one exists — never overwrites
                # a variable that's already set in the shell/CI, so real deployments
                # that inject secrets another way are unaffected.

from extraction import OpenAIExtractorClient
from validation import apply_extraction
from models import UserProfile


SAMPLE_TEXT = (
    "I used to garden with my husband, and I really miss having someone to "
    "talk to about gardening. I also love old jazz and watching basketball."
)


def main():
    try:
        client = OpenAIExtractorClient()
    except RuntimeError as e:
        print(f"Setup problem: {e}")
        sys.exit(1)

    print(f"Using model: {client.model}")
    print(f"Sending to OpenAI: {SAMPLE_TEXT!r}\n")

    try:
        raw_extraction = client.extract(SAMPLE_TEXT)
    except Exception as e:
        print(f"OpenAI call failed: {type(e).__name__}: {e}")
        sys.exit(1)

    print("Raw JSON returned by OpenAI:")
    print(json.dumps(raw_extraction, indent=2))
    print()

    # Run it through the SAME validation/merge logic the real app uses -
    # this confirms the live API's output shape actually matches what
    # validation.py expects, not just that the API call succeeded.
    profile = UserProfile(user_id="live_test_user")
    clarifications = apply_extraction(profile, SAMPLE_TEXT, raw_extraction, client)

    print("Profile after validation:")
    print(json.dumps(profile.to_dict(), indent=2))

    if clarifications:
        print("\nClarification question(s) the app would ask next:")
        for q in clarifications:
            print(f"  - {q}")

    if not profile.interests:
        print(
            "\nWARNING: no interests were stored. Either OpenAI didn't extract any "
            "(unlikely for this sample text), or validation's groundedness check is "
            "rejecting them - print raw_extraction above and compare source_phrase "
            "values against SAMPLE_TEXT."
        )
    else:
        print("\nSuccess: real OpenAI extraction -> validation -> structured profile, end to end.")


if __name__ == "__main__":
    main()