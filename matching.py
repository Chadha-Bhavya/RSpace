"""
Deterministic matching/scoring.

This is the one part of the system that must NEVER call an LLM: the same
two profiles must always produce the same score and the same
explanation. OpenAI's job ends the moment a UserProfile exists — from
here on it's plain, auditable Python.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models import MatchResult, STRENGTH_WEIGHT, UserProfile

# Weights across comparison dimensions; they sum to 1.0. If a dimension
# can't be compared (missing data on either side), its weight is excluded
# and the remaining weights are renormalized — see compute_match(). This
# means missing information shrinks what's being compared rather than
# silently penalizing the score.
DIMENSION_WEIGHTS: Dict[str, float] = {
    "interests": 0.45,
    "location": 0.20,
    "language": 0.15,
    "availability": 0.10,
    "comm_mode": 0.10,
}


def _interest_score(a: UserProfile, b: UserProfile) -> Optional[Tuple[float, List[str]]]:
    """Weighted-Jaccard overlap of interest topics. Each shared topic
    contributes according to both people's engagement strength
    (frequent/occasional/former) and how confident the extraction was —
    a shared "frequent, high-confidence" interest counts more than a
    shared "former, low-confidence" one."""
    if not a.interests or not b.interests:
        return None
    shared = set(a.interests) & set(b.interests)
    union = set(a.interests) | set(b.interests)
    if not union:
        return None
    if not shared:
        return 0.0, []

    total = 0.0
    for topic in shared:
        ia, ib = a.interests[topic], b.interests[topic]
        strength_component = (STRENGTH_WEIGHT[ia.strength] + STRENGTH_WEIGHT[ib.strength]) / 2
        confidence_component = (ia.confidence + ib.confidence) / 2
        total += strength_component * confidence_component

    score = total / len(union)
    return min(score, 1.0), sorted(shared)


def _location_score(a: UserProfile, b: UserProfile) -> Optional[float]:
    if not a.location or not b.location:
        return None
    return 1.0 if a.location.value == b.location.value else 0.0


def _language_score(a: UserProfile, b: UserProfile) -> Optional[float]:
    if not a.languages or not b.languages:
        return None
    return 1.0 if (a.languages & b.languages) else 0.0


def _availability_score(a: UserProfile, b: UserProfile) -> Optional[float]:
    if not a.availability or not b.availability:
        return None
    shared = a.availability & b.availability
    union = a.availability | b.availability
    return len(shared) / len(union) if union else None


def _comm_mode_score(a: UserProfile, b: UserProfile) -> Optional[float]:
    if not a.preferred_comm_mode or not b.preferred_comm_mode:
        return None
    return 1.0 if a.preferred_comm_mode == b.preferred_comm_mode else 0.0


def compute_match(a: UserProfile, b: UserProfile) -> MatchResult:
    breakdown: Dict[str, float] = {}
    shared_interests: List[str] = []
    used_weight = 0.0
    weighted_sum = 0.0

    interest_result = _interest_score(a, b)
    if interest_result is not None:
        score, shared_interests = interest_result
        w = DIMENSION_WEIGHTS["interests"]
        breakdown["interests"] = score
        weighted_sum += score * w
        used_weight += w

    for dim, fn in (
        ("location", _location_score),
        ("language", _language_score),
        ("availability", _availability_score),
        ("comm_mode", _comm_mode_score),
    ):
        score = fn(a, b)
        if score is not None:
            w = DIMENSION_WEIGHTS[dim]
            breakdown[dim] = score
            weighted_sum += score * w
            used_weight += w

    final_score = (weighted_sum / used_weight) if used_weight > 0 else 0.0

    return MatchResult(
        other_user_id=b.user_id,
        score=round(final_score, 3),
        breakdown={k: round(v, 3) for k, v in breakdown.items()},
        shared_interests=shared_interests,
        explanation=_build_explanation(a, b, breakdown, shared_interests),
    )


def _build_explanation(a: UserProfile, b: UserProfile, breakdown: Dict[str, float],
                        shared_interests: List[str]) -> str:
    parts = []
    if shared_interests:
        described = []
        for topic in shared_interests:
            sa, sb = a.interests[topic].strength.value, b.interests[topic].strength.value
            label = topic.replace("_", " ")
            described.append(f"{label} ({sa})" if sa == sb else f"{label} (you: {sa}, them: {sb})")
        parts.append("shared interests: " + ", ".join(described))
    if breakdown.get("location") == 1.0 and a.location:
        parts.append(f"both in {a.location.value}")
    if breakdown.get("language") == 1.0:
        parts.append("share a language")
    if breakdown.get("availability", 0) > 0:
        parts.append("overlapping availability")
    if breakdown.get("comm_mode") == 1.0 and a.preferred_comm_mode:
        parts.append(f"both prefer {a.preferred_comm_mode.value}")
    if not parts:
        return "No strong overlap found yet, but there's not much information to go on either."
    return "Matched on " + "; ".join(parts) + "."