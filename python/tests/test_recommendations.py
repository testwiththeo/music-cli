"""Port of the TypeScript tests/recommendations.test.ts."""

import unittest

from music_cli.recommendations import RecommendationTrack, build_recommendation_query, pick_recommendation


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


if __name__ == "__main__":
    unittest.main()
