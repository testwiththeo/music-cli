"""ANSI terminal UI helpers: banner, cards, status lines, spinner, progress.

Port of the TypeScript ``src/ui.ts``. A lock guards redraws so the playback
ticker and keyboard threads never interleave partial lines.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
from types import SimpleNamespace
from typing import Callable, Literal, TypeVar

T = TypeVar("T")

ESC = "\x1b["
_use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

# Keeps multi-threaded progress redraws and status prints from interleaving.
_OUT_LOCK = threading.Lock()


def _color(code: int, value: str) -> str:
    return f"{ESC}{code}m{value}{ESC}0m" if _use_color else value


def bold(value: str) -> str:
    return _color(1, value)


def dim(value: str) -> str:
    return _color(2, value)


def cyan(value: str) -> str:
    return _color(36, value)


def magenta(value: str) -> str:
    return _color(35, value)


def green(value: str) -> str:
    return _color(32, value)


def yellow(value: str) -> str:
    return _color(33, value)


def red(value: str) -> str:
    return _color(31, value)


def visible_length(value: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", value))


def truncate(value: str, width: int) -> str:
    if width < 4 or visible_length(value) <= width:
        return value
    return value[: max(0, width - 3)] + "..."


def terminal_width() -> int:
    columns = shutil.get_terminal_size().columns
    return columns if columns >= 40 else 80


def print_banner() -> None:
    if not sys.stdout.isatty():
        print("music-cli")
        return

    print(cyan("  __  __ _   _ ____ ___ ____  "))
    print(cyan(" |  \\/  | | | / ___|_ _/ ___| ") + magenta(" // CLI"))
    print(cyan(" | |\\/| | | | \\___ \\| |\\___ \\"))
    print(cyan(" | |  | | |_| |___) | | ___) |"))
    print(cyan(" |_|  |_|\\___/|____/___|____/ "))
    print(dim("  terminal sound system · search / stream / focus\n"))


def print_card(title: str, lines: list[str]) -> None:
    with _OUT_LOCK:
        inner_width = max(36, min(terminal_width() - 4, 76))
        border = cyan("─" * inner_width)
        print(f"  {cyan('╭')}{border}{cyan('╮')}")
        heading = bold(truncate(title, inner_width - 2))
        padding = " " * max(0, inner_width - 1 - visible_length(heading))
        print(f"  {cyan('│')} {heading}{padding}{cyan('│')}")
        for line in lines:
            text = truncate(line, inner_width - 2)
            padding = " " * max(0, inner_width - 1 - visible_length(text))
            print(f"  {cyan('│')} {text}{padding}{cyan('│')}")
        print(f"  {cyan('╰')}{border}{cyan('╯')}")


StatusKind = Literal["info", "success", "warning", "error"]

_STATUS_STYLES: dict[str, tuple[str, Callable[[str], str]]] = {
    "info": ("◆", cyan),
    "success": ("●", green),
    "warning": ("▲", yellow),
    "error": ("×", red),
}


def print_status(kind: StatusKind, message: str) -> None:
    icon, paint = _STATUS_STYLES[kind]
    with _OUT_LOCK:
        print(f"{paint(icon)} {message}")


def with_spinner(label: str, operation: Callable[[], T]) -> T:
    if not sys.stdout.isatty():
        return operation()

    frames = ["·", "✦", "✧", "✦"]
    state = {"index": 0}
    stop = threading.Event()

    def render() -> None:
        frame = frames[state["index"] % len(frames)]
        with _OUT_LOCK:
            sys.stdout.write(f"\r{magenta(frame)} {dim(label)}")
            sys.stdout.flush()

    render()

    def spin() -> None:
        while not stop.wait(0.110):
            state["index"] += 1
            render()

    spinner = threading.Thread(target=spin, daemon=True)
    spinner.start()
    try:
        return operation()
    finally:
        stop.set()
        spinner.join(timeout=0.5)
        with _OUT_LOCK:
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()


def render_progress(current: float, total: float, label: str = "Elapsed") -> None:
    elapsed = format_time(current)
    total_label = format_time(total) if total > 0 else "--:--"
    percentage = min(current / total, 1) if total > 0 else 0
    suffix = f" {int(percentage * 100)}%" if total > 0 else ""
    available = terminal_width() - visible_length(f"{label}  {elapsed} / {total_label}{suffix}") - 8
    bar_width = max(8, min(32, available))
    filled = int(bar_width * percentage) if total > 0 else 0
    bar = green("━" * filled) + dim("━" * (bar_width - filled))
    pulse = ".:=#"
    meter = "".join(pulse[(int(current) + index * 3) % len(pulse)] for index in range(8))
    line = f"{magenta(label)} {bar} {bold(f'{elapsed} / {total_label}')}{dim(suffix)} {cyan(meter)}"

    with _OUT_LOCK:
        if sys.stdout.isatty():
            sys.stdout.write(f"\r\x1b[2K{line}")
            sys.stdout.flush()
        elif current == 0 or current % 30 == 0:
            print(f"{label} {elapsed} / {total_label}{suffix}")


def format_time(seconds: float) -> str:
    seconds = max(0, seconds)
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


#: Namespace kept for parity with the TypeScript ``ui`` export (ui.cyan(...) ...).
ui = SimpleNamespace(bold=bold, cyan=cyan, dim=dim, green=green, magenta=magenta, yellow=yellow, red=red)

__all__ = [
    "bold", "cyan", "dim", "format_time", "green", "magenta", "print_banner",
    "print_card", "print_status", "red", "render_progress", "terminal_width",
    "truncate", "ui", "visible_length", "with_spinner", "yellow",
]
