"""Local taste profile — the data layer for personalized radio.

Replaces Spotify's server-side taste profile with a local one: plays and
skips per artist. Stored under the platform data directory (XDG on Linux,
Application Support on macOS, APPDATA on Windows). No accounts, no telemetry
— the profile never leaves the machine.

On-disk schema (taste.json)::

    {
      "version": 1,
      "artists": {
        "<artist name lowercased>": {
          "plays": <int>, "skips": <int>, "last_played": <unix seconds float>
        }
      }
    }

Deliberately excludes search queries: the PRD requires that no search
history is persisted in the first release.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Optional

from .recommendations import RecommendationTrack

PROFILE_VERSION = 1
MAX_ARTISTS = 200


@dataclass
class ArtistStats:
    plays: int = 0
    skips: int = 0
    last_played: float = 0.0


@dataclass
class TasteProfile:
    version: int = PROFILE_VERSION
    artists: Dict[str, ArtistStats] = field(default_factory=dict)

    def artist_stats(self, artist: str) -> Optional[ArtistStats]:
        return self.artists.get(artist.strip().lower())


def profile_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "music-cli" / "taste.json"


def load_profile() -> TasteProfile:
    """Load the profile; a missing or corrupt file yields a fresh profile."""
    path = profile_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return TasteProfile()
    if not isinstance(data, dict):
        return TasteProfile()
    profile = TasteProfile(version=data.get("version", PROFILE_VERSION))
    for name, stats in (data.get("artists") or {}).items():
        if isinstance(stats, dict):
            profile.artists[name] = ArtistStats(
                plays=int(stats.get("plays", 0)),
                skips=int(stats.get("skips", 0)),
                last_played=float(stats.get("last_played", 0.0)),
            )
    return profile


def save_profile(profile: TasteProfile) -> None:
    """Write atomically (tmp file + rename) and prune stale, low-signal artists."""
    cutoff = time.time() - 180 * 86400
    active = {
        name: stats
        for name, stats in profile.artists.items()
        if stats.last_played >= cutoff or stats.plays + stats.skips >= 3
    }
    if len(active) > MAX_ARTISTS:
        ranked = sorted(active.items(), key=lambda kv: (-(kv[1].plays + kv[1].skips), -kv[1].last_played))
        active = dict(ranked[:MAX_ARTISTS])
    profile.artists = active

    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": profile.version,
        "artists": {
            name: {"plays": s.plays, "skips": s.skips, "last_played": s.last_played}
            for name, s in profile.artists.items()
        },
    }
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".taste-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def record_play(profile: TasteProfile, track: RecommendationTrack) -> None:
    _record(profile, track, played=True)


def record_skip(profile: TasteProfile, track: RecommendationTrack) -> None:
    _record(profile, track, played=False)


def _record(profile: TasteProfile, track: RecommendationTrack, played: bool) -> None:
    key = track.artist.strip().lower()
    if not key:
        return
    stats = profile.artists.get(key, ArtistStats())
    now = time.time()
    if played:
        stats = replace(stats, plays=stats.plays + 1, last_played=now)
    else:
        stats = replace(stats, skips=stats.skips + 1)
    profile.artists[key] = stats
