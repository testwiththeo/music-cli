"""Relevance-ranked autoplay.

Port of the TypeScript ``src/recommendations.ts``. Ranks unplayed candidates
using the active track and the listener's original search as lightweight
taste signals. A stable tie-break preserves provider order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AbstractSet, Optional, Sequence

_TOKEN_PATTERN = re.compile(r"[^a-z0-9\s]")
_STOP_WORDS = {"official", "video", "audio", "music"}


@dataclass
class RecommendationTrack:
    id: str
    title: str
    artist: str


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
) -> Optional[RecommendationTrack]:
    """Rank unplayed candidates using the active track and the listener's
    original search as lightweight taste signals. A stable tie-break
    preserves provider order."""
    current_title = _tokens(current.title)
    current_artist = _tokens(current.artist)
    query_tokens = _tokens(source_query)

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
