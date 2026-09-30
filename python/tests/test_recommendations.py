"""Port of the TypeScript tests/recommendations.test.ts, plus the personal-radio
scoring signals (taste boost, skip penalty, popularity, duration, diversity)."""

import unittest

from music_cli.recommendations import RecommendationTrack, build_recommendation_query, pick_recommendation
from music_cli.taste import ArtistStats, TasteProfile


class RecommendationsTest(unittest.TestCase):
    def setUp(self):
        self.current = RecommendationTrack(id="current", title="Midnight Loops", artist="Nujabes")

    def test_prefers_an_unplayed_track_by_the_current_artist(self):
        result = pick_recommendation(
            self.current,
            [
                self.current,
                RecommendationTrack(id="similar-title", title="Midnight Loops", artist="Nujabes"),
                RecommendationTrack(id="artist-match", title="Feather", artist="Nujabes"),
                RecommendationTrack(id="query-match", title="Lofi Hip Hop Mix", artist="Various Artists"),
            ],
            "lofi hip hop",
            {"current"},
        )
        self.assertEqual(result.id if result else None, "artist-match")

    def test_never_recommends_a_previously_played_candidate(self):
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="played", title="Feather", artist="Nujabes"),
                RecommendationTrack(id="next", title="Aruarian Dance", artist="Nujabes"),
            ],
            "lofi",
            {"played"},
        )
        self.assertEqual(result.id if result else None, "next")

    def test_builds_a_provider_query_from_artist_and_listener_context(self):
        self.assertEqual(build_recommendation_query(self.current, "lofi hip hop"), "Nujabes lofi hip hop music")

    def test_filters_noise_tokens_from_titles(self):
        # "official video audio music" tokens are ignored by the scorer.
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="noise", title="Midnight Loops Official Video", artist="Nujabes"),
            ],
            "lofi",
            set(),
        )
        self.assertEqual(result.id if result else None, "noise")


class PersonalRadioScoringTest(unittest.TestCase):
    def setUp(self):
        self.current = RecommendationTrack(id="current", title="Midnight Loops", artist="Nujabes")

    def test_familiar_artist_beats_query_match(self):
        taste = TasteProfile(artists={"odyssey": ArtistStats(plays=3)})
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="stranger", title="AAA", artist="Odyssey"),
                RecommendationTrack(id="query-match", title="Lofi Hip Hop Mix", artist="Various Artists"),
            ],
            "lofi",
            set(),
            taste_profile=taste,
        )
        self.assertEqual(result.id if result else None, "stranger")

    def test_familiar_artist_loses_without_a_profile(self):
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="stranger", title="AAA", artist="Odyssey"),
                RecommendationTrack(id="query-match", title="Lofi Hip Hop Mix", artist="Various Artists"),
            ],
            "lofi",
            set(),
        )
        self.assertEqual(result.id if result else None, "query-match")

    def test_skipped_artist_is_demoted(self):
        taste = TasteProfile(artists={"skipped one": ArtistStats(skips=2)})
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="skipped", title="AAA", artist="Skipped One"),
                RecommendationTrack(id="neutral", title="BBB", artist="Someone Else"),
            ],
            "",
            set(),
            taste_profile=taste,
        )
        self.assertEqual(result.id if result else None, "neutral")

    def test_long_mix_is_demoted_for_short_current_track(self):
        current = RecommendationTrack(id="current", title="Midnight Loops", artist="Nujabes", duration_seconds=180)
        result = pick_recommendation(
            current,
            [
                RecommendationTrack(id="mix", title="Lofi Hip Hop Mix", artist="Various Artists", duration_seconds=7200),
                RecommendationTrack(id="song", title="BBB", artist="Someone Else", duration_seconds=200),
            ],
            "lofi",
            set(),
        )
        self.assertEqual(result.id if result else None, "song")

    def test_popularity_breaks_relevance_ties(self):
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="popular", title="AAA", artist="X", view_count=10_000_000),
                RecommendationTrack(id="relevant", title="Lofi", artist="Y"),
            ],
            "lofi",
            set(),
        )
        self.assertEqual(result.id if result else None, "popular")

    def test_monotony_penalty_varies_repeated_artist(self):
        result = pick_recommendation(
            self.current,
            [
                RecommendationTrack(id="same-again", title="AAA", artist="Nujabes"),
                RecommendationTrack(id="fresh", title="BBB", artist="Someone Else"),
            ],
            "",
            set(),
            recent_artists=["Nujabes", "Nujabes", "Nujabes"],
        )
        self.assertEqual(result.id if result else None, "fresh")


if __name__ == "__main__":
    unittest.main()
