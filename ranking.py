"""
Ranking — score one user against a pool of candidates and return the top
matches. Deterministic, same as matching.py.
"""

from __future__ import annotations

from typing import List

from matching import compute_match
from models import MatchResult, UserProfile

# Below this, a "match" is more noise than signal.
MIN_MATCH_SCORE = 0.15


def find_matches(user: UserProfile, candidates: List[UserProfile], top_n: int = 5) -> List[MatchResult]:
    """Scores `user` against every candidate, filters out very weak
    matches, and returns the top N sorted by score (descending).

    If nothing clears MIN_MATCH_SCORE (common for a brand-new,
    barely-answered profile), falls back to the best few anyway rather
    than returning nothing — a mediocre conversation starter beats an
    empty screen for someone who's isolated.
    """
    results = [
        compute_match(user, other)
        for other in candidates
        if other.user_id != user.user_id
    ]
    results.sort(key=lambda r: r.score, reverse=True)

    strong = [r for r in results if r.score >= MIN_MATCH_SCORE]
    pool = strong if strong else results
    return pool[:top_n]