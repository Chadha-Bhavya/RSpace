# RSpace


Readme · MD
# Senior Social Matching — Backend MVP
 
## Files
 
- `models.py` — data model (`UserProfile`, `ExtractedInterest`, `MatchResult`, etc.)
- `extraction.py` — the only file that talks to OpenAI. Defines `ExtractorClient`
  (a Protocol), a real `OpenAIExtractorClient`, and a deterministic
  `MockExtractorClient` used in tests/demo.
- `validation.py` — confidence thresholds, anti-hallucination checks, and the
  decision of when to ask a clarifying follow-up. Pure Python, no LLM calls.
- `matching.py` — deterministic weighted scoring between two profiles. No LLM
  calls, ever.
- `ranking.py` — scores one user against a candidate pool and returns the
  top matches.
- `tests.py` — unit tests (strong/weak/partial/missing/ambiguous/hallucinated/
  no-overlap/ranking).
- `demo.py` — runnable end-to-end example, raw text → match explanation.
## Running it
 
```bash
cd senior_match
python3 demo.py                       # end-to-end demo, no API key needed
python3 -m unittest tests.py -v       # unit tests, no API key needed
```
 
## Using real OpenAI extraction
 
```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini       # optional, this is already the default
pip install openai
```
 
Then in your own code (or `demo.py`):
 
```python
from extraction import OpenAIExtractorClient
client = OpenAIExtractorClient()
```
 
Everything else — `validation.py`, `matching.py`, `ranking.py` — is unchanged,
because they only depend on the `ExtractorClient` protocol, not on OpenAI
directly.
 
## Why the LLM never touches the score
 
`extraction.py` only produces structured JSON (interests, location,
availability, etc.) with confidence values. `validation.py` decides what to
trust. `matching.py` turns two trusted profiles into a score using fixed,
readable weights. If a match looks wrong, the bug is findable in one of
three small files — never inside a prompt.
 

