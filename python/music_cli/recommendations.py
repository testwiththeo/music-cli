"""Relevance-ranked autoplay.

Port of the TypeScript ``src/recommendations.ts``. Ranks unplayed candidates
using the active track and the listener's original search as lightweight
taste signals. A stable tie-break preserves provider order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AbstractSet, Optional, Sequence

import math

_TOKEN_PATTERN = re.compile(r"[^a-z0-9\s]")
_STOP_WORDS = {"official", "video", "audio", "music"}

POPULARITY_MAX_BOOST = 8
FAMILIARITY_MAX_BOOST = 24
FAMILIARITY_PER_PLAY = 8
SKIP_PENALTY = 15
DURATION_PENALTY_MAX = 15
DURATION_PENALTY_PER_OCTAVE = 5
MONOTONY_PENALTY = 60  # must outweigh the same-artist bonus (40) plus artist overlap (12)


@dataclass
class RecommendationTrack:
    id: str
    title: str
    artist: str
    view_count: int = 0
    duration_seconds: int = 0


def _tokens(value: str) -> set[str]:
    words = _TOKEN_PATTERN.sub(" ", value.lower()).split()
    return {word for word in words if len(word) > 2 and word not in _STOP_WORDS}


def _overlap(left: set[str], right: set[str]) -> int:
    return sum(1 for word in left if word in right)


def _is_same_track(left: RecommendationTrack, right: RecommendationTrack) -> bool:
    return left.id == right.id or (
        left.title.strip().lower() == right.title.strip().lower()
        and left.artist.strip().lower() == right.artist.strip().lower()
    )


def pick_recommendation(
    current: RecommendationTrack,
    candidates: Sequence[RecommendationTrack],
    source_query: str,
    played_ids: AbstractSet[str],
    taste_profile=None,
    recent_artists: Sequence[str] = (),
) -> Optional[RecommendationTrack]:
    """Rank unplayed candidates using the active track, the listener's original
    search, and — when a taste profile is given — their local play/skip history,
    as lightweight taste signals. A stable tie-break preserves provider order."""
    current_title = _tokens(current.title)
    current_artist = _tokens(current.artist)
    query_tokens = _tokens(source_query)
    recent = [artist.strip().lower() for artist in recent_artists][-3:]
    monotony = len(recent) == 3 and len(set(recent)) == 1

    best: Optional[RecommendationTrack] = None
    best_score = -1

    for candidate in candidates:
        if candidate.id in played_ids or _is_same_track(candidate, current):
            continue

        candidate_title = _tokens(candidate.title)
        candidate_artist = _tokens(candidate.artist)
        same_artist = candidate.artist.strip().lower() == current.artist.strip().lower()
        score = (
            (40 if same_artist else 0)
            + _overlap(current_artist, candidate_artist) * 12
            + _overlap(current_title, candidate_title) * 5
            + _overlap(query_tokens, candidate_title) * 3
            + _overlap(query_tokens, candidate_artist) * 2
        )

        if taste_profile is not None:
            stats = taste_profile.artist_stats(candidate.artist)
            if stats is not None:
                score += min(FAMILIARITY_MAX_BOOST, stats.plays * FAMILIARITY_PER_PLAY)
                score -= stats.skips * SKIP_PENALTY

        if candidate.view_count > 0:
            score += min(POPULARITY_MAX_BOOST, int(math.log10(candidate.view_count)))

        if current.duration_seconds > 0 and candidate.duration_seconds > 0:
            ratio = max(candidate.duration_seconds / current.duration_seconds,
                        current.duration_seconds / candidate.duration_seconds)
            if ratio >= 4:
                score -= min(DURATION_PENALTY_MAX, int(math.log2(ratio) * DURATION_PENALTY_PER_OCTAVE))

        if monotony and candidate.artist.strip().lower() == recent[0]:
            score -= MONOTONY_PENALTY

        if score > best_score:
            best = candidate
            best_score = score

    return best


def build_recommendation_query(current: RecommendationTrack, source_query: str) -> str:
    artist = current.artist.strip()
    context = source_query.strip()
    if artist and context:
        return f"{artist} {context} music"
    return f"{artist or context} music"
