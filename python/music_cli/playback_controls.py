"""Keyboard mapping for playback controls.

Port of the TypeScript ``src/playback-controls.ts``. Keys arrive as raw byte
chunks: arrow keys are the three-byte escape sequences, a plain Escape is a
single byte.
"""

from __future__ import annotations

SEEK_SECONDS = 5

_RIGHT_ARROW = b"\x1b[C"
_LEFT_ARROW = b"\x1b[D"


def seek_offset_for_key(key: bytes) -> int | None:
    """Map the right/left arrow sequences to ±SEEK_SECONDS; None otherwise."""
    if key == _RIGHT_ARROW:
        return SEEK_SECONDS
    if key == _LEFT_ARROW:
        return -SEEK_SECONDS
    return None


def is_escape_key(key: bytes) -> bool:
    """A plain Escape is one byte; arrow keys begin with Escape but are longer."""
    return len(key) == 1 and key[0] == 27
