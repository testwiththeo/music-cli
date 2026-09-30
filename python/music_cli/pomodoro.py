"""Pomodoro configuration, session planning, and CLI flag parsing.

Port of the TypeScript ``src/pomodoro.ts`` — pure and testable. Number
coercion deliberately mirrors JavaScript's ``Number()`` so flag values like
``--focus`` (missing value → ``0``) fail validation the same way.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Literal, Optional

Phase = Literal["focus", "shortBreak", "longBreak"]


@dataclass
class PomodoroConfig:
    focus_minutes: float
    short_break_minutes: float
    long_break_minutes: float
    cycles_before_long_break: int


@dataclass
class PomodoroPlanItem:
    phase: Phase
    focus_number: int  # 1-based, which focus this item belongs to / follows
    duration_seconds: int
    label: str


DEFAULT_POMODORO_CONFIG = PomodoroConfig(
    focus_minutes=25,
    short_break_minutes=5,
    long_break_minutes=15,
    cycles_before_long_break=4,
)

POMODORO_PRESETS: dict[str, PomodoroConfig] = {
    "classic": PomodoroConfig(focus_minutes=25, short_break_minutes=5, long_break_minutes=15, cycles_before_long_break=4),
    "deep": PomodoroConfig(focus_minutes=50, short_break_minutes=10, long_break_minutes=30, cycles_before_long_break=2),
    "sprint": PomodoroConfig(focus_minutes=15, short_break_minutes=3, long_break_minutes=10, cycles_before_long_break=4),
}


def _js_round(value: float) -> int:
    """JavaScript Math.round (half away from zero; inputs here are positive)."""
    return math.floor(value + 0.5)


def _js_number(raw: str) -> float:
    """JavaScript ``Number()`` semantics for flag values: '' → 0, non-numeric → NaN."""
    stripped = raw.strip()
    if not stripped:
        return 0.0
    try:
        return float(stripped)
    except ValueError:
        return math.nan


def validate_pomodoro_config(config: PomodoroConfig) -> Optional[str]:
    if not math.isfinite(config.focus_minutes) or config.focus_minutes < 1 or config.focus_minutes > 180:
        return "Invalid --focus: expected 1-180 minutes."
    if not math.isfinite(config.short_break_minutes) or config.short_break_minutes < 1 or config.short_break_minutes > 60:
        return "Invalid --break: expected 1-60 minutes."
    if not math.isfinite(config.long_break_minutes) or config.long_break_minutes < 1 or config.long_break_minutes > 90:
        return "Invalid --long-break: expected 1-90 minutes."
    cycles = config.cycles_before_long_break
    if not math.isfinite(cycles) or not float(cycles).is_integer() or cycles < 1 or cycles > 12:
        return "Invalid --cycles: expected integer 1-12."
    return None


def get_phase_duration_seconds(phase: Phase, config: PomodoroConfig) -> int:
    minutes = {
        "focus": config.focus_minutes,
        "shortBreak": config.short_break_minutes,
        "longBreak": config.long_break_minutes,
    }[phase]
    return _js_round(minutes * 60)


def format_countdown(total_seconds: float) -> str:
    s = max(0, math.floor(total_seconds))
    return f"{s // 60}:{s % 60:02d}"


def phase_label(phase: Phase, focus_number: int, total_cycles: int) -> str:
    if phase == "focus":
        return f"Focus {focus_number}/{total_cycles}"
    if phase == "shortBreak":
        return f"Short break after focus {focus_number}"
    return "Long break"


def build_session_plan(config: PomodoroConfig, total_focuses: Optional[int] = None) -> list[PomodoroPlanItem]:
    """Build a full session plan: focus, break, focus, break … ending with a long break."""
    n = config.cycles_before_long_break if total_focuses is None else total_focuses
    # Cycle counts parse through Number() and may arrive as 2.0-style floats;
    # validation guarantees they are whole before they reach the plan.
    n = int(n)
    plan: list[PomodoroPlanItem] = []
    for i in range(1, n + 1):
        plan.append(PomodoroPlanItem(
            phase="focus",
            focus_number=i,
            duration_seconds=get_phase_duration_seconds("focus", config),
            label=phase_label("focus", i, n),
        ))
        if i < n:
            plan.append(PomodoroPlanItem(
                phase="shortBreak",
                focus_number=i,
                duration_seconds=get_phase_duration_seconds("shortBreak", config),
                label=phase_label("shortBreak", i, n),
            ))
        else:
            plan.append(PomodoroPlanItem(
                phase="longBreak",
                focus_number=i,
                duration_seconds=get_phase_duration_seconds("longBreak", config),
                label=phase_label("longBreak", i, n),
            ))
    return plan


@dataclass
class ParsedPomodoroCli:
    enabled: bool
    config: PomodoroConfig
    query: Optional[str] = None
    break_query: Optional[str] = None
    error: Optional[str] = None


def _take_value(argv: list[str], names: list[str]) -> Optional[str]:
    """Flag reader mirroring the TypeScript original: supports ``--name value``
    and ``--name=value``; returns ``""`` when the flag is present without a
    usable value, and ``None`` when the flag is absent."""
    for name in names:
        if name in argv:
            index = argv.index(name)
            value = argv[index + 1] if index + 1 < len(argv) else None
            if value is None or value.startswith("--"):
                return ""
            return value
        for item in argv:
            if item.startswith(f"{name}="):
                return item[len(name) + 1:]
    return None


def parse_pomodoro_cli_args(argv: list[str]) -> ParsedPomodoroCli:
    """Minimal flag parser for pomodoro-related args. Pure + testable."""
    enabled = "--pomodoro" in argv
    config = replace(DEFAULT_POMODORO_CONFIG)
    query: Optional[str] = None
    break_query: Optional[str] = None

    preset_name = _take_value(argv, ["--preset"])
    if preset_name is not None:
        preset = POMODORO_PRESETS.get(preset_name)
        if preset is None:
            return ParsedPomodoroCli(
                enabled=enabled,
                config=config,
                error=f'Unknown --preset "{preset_name}". Try classic|deep|sprint.',
            )
        config = replace(preset)

    focus_raw = _take_value(argv, ["--focus"])
    break_raw = _take_value(argv, ["--break", "--short-break"])
    long_raw = _take_value(argv, ["--long-break"])
    cycles_raw = _take_value(argv, ["--cycles"])
    query_raw = _take_value(argv, ["--query"])
    break_query_raw = _take_value(argv, ["--break-query"])

    if focus_raw is not None:
        config.focus_minutes = _js_number(focus_raw)
    if break_raw is not None:
        config.short_break_minutes = _js_number(break_raw)
    if long_raw is not None:
        config.long_break_minutes = _js_number(long_raw)
    if cycles_raw is not None:
        config.cycles_before_long_break = _js_number(cycles_raw)
    if query_raw is not None:
        query = query_raw
    if break_query_raw is not None:
        break_query = break_query_raw

    if enabled:
        error = validate_pomodoro_config(config)
        if error:
            return ParsedPomodoroCli(enabled=enabled, config=config, query=query, break_query=break_query, error=error)
    return ParsedPomodoroCli(enabled=enabled, config=config, query=query, break_query=break_query)
