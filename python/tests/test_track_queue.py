"""Tests for the in-memory FIFO track queue (Phase 1)."""

import unittest

from music_cli.track_queue import TrackQueue
from music_cli.youtube import VideoInfo


def make_video(video_id: str) -> VideoInfo:
    return VideoInfo(
        title=f"Track {video_id}",
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        duration_seconds=180,
        duration_timestamp="3:00",
        author_name="Nujabes",
    )


class TrackQueueTest(unittest.TestCase):
    def test_pops_in_fifo_order(self):
        queue = TrackQueue()
        queue.add(make_video("a"))
        queue.add(make_video("b"))
        queue.add(make_video("c"))
        self.assertEqual(queue.pop().video_id, "a")
        self.assertEqual(queue.pop().video_id, "b")
        self.assertEqual(queue.pop().video_id, "c")

    def test_pop_on_empty_queue_returns_none(self):
        self.assertIsNone(TrackQueue().pop())

    def test_peek_does_not_consume(self):
        queue = TrackQueue()
        queue.add(make_video("a"))
        self.assertEqual(queue.peek().video_id, "a")
        self.assertEqual(len(queue), 1)

    def test_items_returns_a_copy(self):
        queue = TrackQueue()
        queue.add(make_video("a"))
        items = queue.items()
        items.clear()
        self.assertEqual(len(queue), 1)

    def test_clear_empties_the_queue(self):
        queue = TrackQueue()
        queue.add(make_video("a"))
        queue.clear()
        self.assertEqual(len(queue), 0)
        self.assertIsNone(queue.pop())

    def test_len_tracks_pending_count(self):
        queue = TrackQueue()
        self.assertEqual(len(queue), 0)
        queue.add(make_video("a"))
        queue.add(make_video("b"))
        self.assertEqual(len(queue), 2)
        queue.pop()
        self.assertEqual(len(queue), 1)


if __name__ == "__main__":
    unittest.main()
