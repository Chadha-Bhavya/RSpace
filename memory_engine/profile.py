from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import MemoryEvent


def build_profile(user_id: str, events: list[MemoryEvent], embedding_backend: str) -> dict[str, Any]:
    interests: dict[str, list[MemoryEvent]] = defaultdict(list)
    relationships: Counter[str] = Counter()
    availability: Counter[str] = Counter()
    communication: Counter[str] = Counter()
    social_events: list[MemoryEvent] = []
    conversation_notes: list[MemoryEvent] = []
    important_dates: list[MemoryEvent] = []
    plans: list[MemoryEvent] = []
    themes: Counter[str] = Counter()

    for event in events:
        if event.kind == "interest":
            interests[event.value].append(event)
        elif event.kind == "relationship":
            relationships[event.value] += 1
        elif event.kind == "availability":
            availability[event.value] += 1
        elif event.kind == "communication_preference":
            communication[event.value] += 1
        elif event.kind == "social_signal":
            social_events.append(event)
        elif event.kind == "conversation_note":
            conversation_notes.append(event)
            themes.update(str(keyword) for keyword in event.attributes.get("keywords", []))
        elif event.kind == "important_date":
            important_dates.append(event)
        elif event.kind == "plan":
            plans.append(event)

    interest_summary = []
    for topic, observations in interests.items():
        latest = max(observations, key=lambda event: event.timestamp)
        positives = sum(event.attributes.get("polarity") == "positive" for event in observations)
        negatives = len(observations) - positives
        interest_summary.append({
            "topic": topic,
            "current_polarity": latest.attributes.get("polarity", "unknown"),
            "strength": latest.attributes.get("strength", "unknown"),
            "confidence": latest.confidence,
            "observations": len(observations),
            "positive_mentions": positives,
            "negative_mentions": negatives,
            "last_seen": latest.timestamp,
            "evidence": latest.evidence,
        })

    interest_summary.sort(key=lambda item: (item["current_polarity"] != "positive", -item["observations"], item["topic"]))
    trend = _social_trend(social_events)
    return {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "embedding_backend": embedding_backend,
        "interests": interest_summary,
        "important_relationships": [
            {"relationship": relationship, "mentions": count}
            for relationship, count in relationships.most_common()
        ],
        "availability": [value for value, _ in availability.most_common()],
        "communication_preferences": [value for value, _ in communication.most_common()],
        "top_themes": [
            {"theme": theme, "mentions": count}
            for theme, count in themes.most_common(10)
        ],
        "recent_memories": [
            {
                "timestamp": event.timestamp,
                "summary": event.value,
                "evidence": event.evidence,
                "confidence": event.confidence,
            }
            for event in sorted(conversation_notes, key=lambda item: item.timestamp, reverse=True)[:10]
        ],
        "important_dates": [
            {
                "value": event.value,
                "person": event.attributes.get("person"),
                "date": event.attributes.get("date"),
                "occasion": event.attributes.get("occasion"),
                "observed_at": event.timestamp,
                "confidence": event.confidence,
            }
            for event in sorted(important_dates, key=lambda item: item.timestamp, reverse=True)[:30]
        ],
        "plans": [
            {
                "value": event.value,
                "date": event.attributes.get("date"),
                "person": event.attributes.get("person"),
                "observed_at": event.timestamp,
                "confidence": event.confidence,
            }
            for event in sorted(plans, key=lambda item: item.timestamp, reverse=True)[:20]
        ],
        "social_wellness": trend,
    }


def _social_trend(events: list[MemoryEvent]) -> dict[str, Any]:
    ordered = sorted(events, key=lambda event: event.timestamp)
    loneliness = [event for event in ordered if event.value == "loneliness"]
    connection = [event for event in ordered if event.value == "social_connection"]
    positive_loneliness = sum(event.attributes.get("polarity") == "positive" for event in loneliness)

    if len(ordered) < 6:
        direction = "insufficient_data"
    else:
        midpoint = len(ordered) // 2
        earlier = ordered[:midpoint]
        recent = ordered[midpoint:]

        def loneliness_rate(items: list[MemoryEvent]) -> float:
            if not items:
                return 0.0
            return sum(
                item.value == "loneliness" and item.attributes.get("polarity") == "positive"
                for item in items
            ) / len(items)

        difference = loneliness_rate(recent) - loneliness_rate(earlier)
        direction = "increasing_signal" if difference > 0.2 else "decreasing_signal" if difference < -0.2 else "stable_signal"

    return {
        "status": direction,
        "loneliness_mentions": positive_loneliness,
        "explicit_not_lonely_mentions": len(loneliness) - positive_loneliness,
        "connection_mentions": len(connection),
        "observations": len(ordered),
        "notice": "Observational signals only; this is not a medical diagnosis.",
    }


def build_wellness_report(profile: dict[str, Any]) -> dict[str, Any]:
    social = profile.get("social_wellness", {})
    observations = int(social.get("observations", 0))
    return {
        "user_id": profile.get("user_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "social_wellness_observation",
        "data_quality": "insufficient_data" if observations < 6 else "observational",
        "summary": (
            "Not enough social-signal observations are available to describe a trend."
            if observations < 6
            else f"The recent loneliness-related signal is {social.get('status', 'unknown').replace('_', ' ')}."
        ),
        "social_wellness": social,
        "interests": profile.get("interests", []),
        "important_relationships": profile.get("important_relationships", []),
        "top_themes": profile.get("top_themes", []),
        "recent_observations": profile.get("recent_memories", [])[:5],
        "disclaimer": (
            "This report summarizes statements made in conversation. It does not diagnose, rule out, "
            "or treat loneliness, depression, dementia, or any other condition. A qualified professional "
            "must interpret it alongside direct assessment and clinical context."
        ),
    }
