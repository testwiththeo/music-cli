"""In-memory FIFO queue of normalized tracks (Phase 1 "Queue Release").

Deliberately minimal: add, pop, peek, clear. Reorder/removal/replay are
Phase 2 work. Popping consumes; stopping playback never pops — so an
interrupted track is not followed by the next queued one.
"""

from __future__ import annotations

from typing import List, Optional

from .youtube import VideoInfo


class TrackQueue:
    """FIFO of tracks waiting to play, in the order the user queued them."""

    def __init__(self) -> None:
        self._items: List[VideoInfo] = []

    def add(self, video: VideoInfo) -> None:
        self._items.append(video)

    def pop(self) -> Optional[VideoInfo]:
        """Take the next track, or None when the queue is empty."""
        if not self._items:
            return None
        return self._items.pop(0)

    def peek(self) -> Optional[VideoInfo]:
        return self._items[0] if self._items else None

    def items(self) -> List[VideoInfo]:
        """A copy of the pending tracks, next-to-play first."""
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
