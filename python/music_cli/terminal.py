"""Raw-mode terminal input helpers (POSIX terminals).

Replaces Node's ``process.stdin.setRawMode``. Input flags are cleared the way
Node does (echo, canonical mode, signals off) while output processing is left
untouched so ``\\n`` still expands to CRLF.
"""

from __future__ import annotations

import os
import select
import sys
import termios
from typing import List, Optional, Union

_TermiosState = List[Union[int, list]]

# How long a lone ESC byte waits for continuation bytes of an escape sequence.
_ESCAPE_FOLLOW_UP_SECONDS = 0.02


def enable_raw_mode() -> Optional[_TermiosState]:
    """Put stdin into raw input mode; returns saved state for restore_raw_mode.

    Returns None when stdin is not a TTY (callers then skip keyboard input).
    """
    if not sys.stdin.isatty():
        return None
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    attrs = termios.tcgetattr(fd)

    # Input flags: cfmakeraw-style, but keep OPOST so printed \n stays CRLF.
    attrs[0] &= ~(
        termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
        | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON
    )
    # Control flags: 8-bit clean, no parity (as Node's raw mode does).
    attrs[2] &= ~(termios.CSIZE | termios.PARENB)
    attrs[2] |= termios.CS8
    # Local flags: no echo, no line buffering, no signal generation —
    # Ctrl+C arrives as byte 0x03, exactly like the TypeScript original.
    attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0

    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return saved


def restore_raw_mode(saved: Optional[_TermiosState]) -> None:
    if saved is None:
        return
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved)


def read_key_chunk(timeout: Optional[float] = None) -> bytes:
    """Read one keypress-sized chunk from stdin; b'' when nothing arrives.

    A lone ESC waits a few milliseconds for continuation bytes so an arrow
    key arrives as a single ``\\x1b[C`` chunk, mirroring the granularity of
    Node's stdin 'data' events. Without a timeout the read blocks forever.
    """
    fd = sys.stdin.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return b""
    data = os.read(fd, 256)
    if data == b"\x1b":
        more, _, _ = select.select([fd], [], [], _ESCAPE_FOLLOW_UP_SECONDS)
        if more:
            data += os.read(fd, 256)
    return data
