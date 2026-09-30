"""Tests for the local taste profile (personal radio data layer)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from music_cli.cli import radio_seed_queries
from music_cli.recommendations import RecommendationTrack
from music_cli.taste import (
    TasteProfile,
    load_profile,
    record_play,
    record_skip,
    save_profile,
)


class TasteProfileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_file_yields_fresh_profile(self):
        self.assertEqual(load_profile().artists, {})

    def test_corrupt_file_yields_fresh_profile(self):
        path = Path(os.environ["XDG_DATA_HOME"]) / "music-cli" / "taste.json"
        path.parent.mkdir(parents=True)
        path.write_text("not json at all", encoding="utf-8")
        self.assertEqual(load_profile().artists, {})

    def test_plays_and_skips_persist(self):
        profile = load_profile()
        track = RecommendationTrack(id="1", title="Feather", artist="Nujabes")
        record_play(profile, track)
        record_play(profile, track)
        record_skip(profile, track)
        save_profile(profile)

        loaded = load_profile()
        stats = loaded.artist_stats("nujabes")
        self.assertEqual(stats.plays, 2)
        self.assertEqual(stats.skips, 1)

    def test_schema_persists_no_search_history(self):
        # PRD non-goal: no search history may be persisted in the first release.
        import json

        profile = TasteProfile()
        record_play(profile, RecommendationTrack(id="1", title="T", artist="Nujabes"))
        save_profile(profile)
        path = Path(os.environ["XDG_DATA_HOME"]) / "music-cli" / "taste.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), {"version", "artists"})

    def test_save_is_atomic_no_tmp_leftover(self):
        profile = TasteProfile()
        record_play(profile, RecommendationTrack(id="1", title="T", artist="Nujabes"))
        save_profile(profile)
        leftovers = list(Path(os.environ["XDG_DATA_HOME"]).rglob(".taste-*.tmp"))
        self.assertEqual(leftovers, [])

    def test_stale_low_signal_artists_are_pruned(self):
        profile = TasteProfile()
        record_play(profile, RecommendationTrack(id="1", title="T", artist="One Hit"))
        stale = profile.artist_stats("one hit")
        stale.last_played = 0.0  # ancient history, single play
        regular = RecommendationTrack(id="2", title="T", artist="Daily Driver")
        for _ in range(5):
            record_play(profile, regular)
        save_profile(profile)

        loaded = load_profile()
        self.assertIsNone(loaded.artist_stats("one hit"))
        self.assertIsNotNone(loaded.artist_stats("daily driver"))


class RadioSeedTest(unittest.TestCase):
    def test_seeds_start_with_artist_and_add_favorites(self):
        profile = TasteProfile()
        record_play(profile, RecommendationTrack(id="1", title="T", artist="Taeko Onuki"))
        record_play(profile, RecommendationTrack(id="2", title="T", artist="Taeko Onuki"))
        record_play(profile, RecommendationTrack(id="3", title="T", artist="Nujabes"))
        one_play = RecommendationTrack(id="4", title="T", artist="One Timer")
        record_play(profile, one_play)
        record_play(profile, one_play)
        record_play(profile, one_play)

        current = RecommendationTrack(id="9", title="Feather", artist="Nujabes")
        seeds = radio_seed_queries_of(current, "lofi", profile)
        # Artist + query first; then favorite artists (≥2 plays) except the current one.
        self.assertEqual(seeds[0], ("Nujabes lofi music", "Nujabes"))
        labels = [label for _, label in seeds[1:]]
        self.assertIn("taeko onuki", labels)
        self.assertIn("one timer", labels)


def radio_seed_queries_of(current, query, profile):
    """Adapt RecommendationTrack current into the cli helper's VideoInfo shape."""
    from music_cli.cli import radio_seed_queries as seeds
    from music_cli.youtube import VideoInfo

    video = VideoInfo(
        title=current.title,
        video_id=current.id,
        url="",
        duration_seconds=0,
        duration_timestamp="0:00",
        author_name=current.artist,
    )
    return seeds(video, query, profile)


if __name__ == "__main__":
    unittest.main()
