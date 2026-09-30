"""Minimal interactive prompts replacing the ``@inquirer/prompts`` dependency.

Both prompts run the terminal in raw mode and cancel on Esc / Ctrl+C by
raising PromptCancelled, which the CLI translates into the same graceful
goodbye the TypeScript version performs when inquirer throws its exit error.
"""

from __future__ import annotations

import sys
from typing import Any, List, Tuple

from . import terminal
from .ui import bold, cyan, dim


class PromptCancelled(Exception):
    """The user pressed Esc or Ctrl+C at a prompt."""


def prompt_input(message: str) -> str:
    """Free-text input with inline editing; Esc / Ctrl+C cancel the prompt."""
    if not sys.stdin.isatty():
        sys.stdout.write(f"{message} ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            raise PromptCancelled("input stream closed")
        return line.rstrip("\n")

    saved = terminal.enable_raw_mode()
    assert saved is not None
    value = ""

    def render() -> None:
        sys.stdout.write(f"\r\x1b[2K{bold(message)} {value}")
        sys.stdout.flush()

    try:
        render()
        while True:
            chunk = terminal.read_key_chunk()
            if chunk in (b"\r", b"\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return value
            if chunk == b"\x03" or chunk == b"\x1b":
                sys.stdout.write("\r\x1b[2K\n")
                sys.stdout.flush()
                raise PromptCancelled("prompt cancelled")
            if chunk in (b"\x7f", b"\x08"):
                value = value[:-1]
            elif chunk == b"\x15":  # Ctrl+U clears the line, readline-style
                value = ""
            else:
                text = chunk.decode("utf-8", errors="ignore")
                value += "".join(char for char in text if char.isprintable())
            render()
    finally:
        terminal.restore_raw_mode(saved)


def prompt_select(message: str, choices: List[Tuple[str, Any]], default_index: int = 0) -> Any:
    """Arrow-key single select over (label, value) choices; Esc / Ctrl+C cancel."""
    if not choices:
        raise PromptCancelled("no choices to select from")

    if not sys.stdin.isatty():
        sys.stdout.write(f"{bold(message)}\n")
        for index, (name, _) in enumerate(choices):
            sys.stdout.write(f"  {index + 1}) {name}\n")
        sys.stdout.write("Number: ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            raise PromptCancelled("input stream closed")
        try:
            index = int(line.strip()) - 1
            if not 0 <= index < len(choices):
                raise ValueError
        except ValueError:
            raise PromptCancelled("invalid selection") from None
        sys.stdout.write(f"{choices[index][0]}\n")
        return choices[index][1]

    saved = terminal.enable_raw_mode()
    assert saved is not None
    selected = max(0, min(default_index, len(choices) - 1))
    row_count = len(choices)
    header = bold(message)

    def render(redraw: bool) -> None:
        parts: List[str] = []
        if redraw:
            parts.append(f"\x1b[{row_count}A")  # back up over the choice rows
        parts.append(f"\r\x1b[2K{header} {dim('(Use arrow keys)')}")
        for index, (name, _) in enumerate(choices):
            pointer = cyan("❯") if index == selected else " "
            parts.append(f"\n\r\x1b[2K{pointer} {name}")
        sys.stdout.write("".join(parts))
        sys.stdout.flush()

    sys.stdout.write("\x1b[?25l")  # hide cursor
    try:
        render(False)
        while True:
            chunk = terminal.read_key_chunk()
            if chunk == b"\x1b[A":
                selected = max(0, selected - 1)
                render(True)
            elif chunk == b"\x1b[B":
                selected = min(row_count - 1, selected + 1)
                render(True)
            elif chunk in (b"\r", b"\n"):
                sys.stdout.write(f"\x1b[{row_count}A\r\x1b[2K{header} {choices[selected][0]}\x1b[J\n")
                sys.stdout.flush()
                return choices[selected][1]
            elif chunk == b"\x03" or chunk == b"\x1b":
                sys.stdout.write(f"\x1b[{row_count}A\r\x1b[2K\x1b[J\n")
                sys.stdout.flush()
                raise PromptCancelled("prompt cancelled")
    finally:
        sys.stdout.write("\x1b[?25h")  # restore cursor
        sys.stdout.flush()
        terminal.restore_raw_mode(saved)
