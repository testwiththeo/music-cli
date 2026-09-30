"""Port of the TypeScript tests/pomodoro.test.ts."""

import unittest
from dataclasses import replace

from music_cli.pomodoro import (
    DEFAULT_POMODORO_CONFIG,
    build_session_plan,
    format_countdown,
    get_phase_duration_seconds,
    parse_pomodoro_cli_args,
    validate_pomodoro_config,
)


class FormatCountdownTest(unittest.TestCase):
    def test_formats_minutes_and_seconds(self):
        self.assertEqual(format_countdown(25 * 60), "25:00")
        self.assertEqual(format_countdown(59), "0:59")
        self.assertEqual(format_countdown(0), "0:00")
        self.assertEqual(format_countdown(-5), "0:00")


class ValidatePomodoroConfigTest(unittest.TestCase):
    def test_accepts_defaults(self):
        self.assertIsNone(validate_pomodoro_config(DEFAULT_POMODORO_CONFIG))

    def test_rejects_out_of_range_durations(self):
        self.assertIn("--focus", validate_pomodoro_config(replace(DEFAULT_POMODORO_CONFIG, focus_minutes=0)))
        self.assertIn("--break", validate_pomodoro_config(replace(DEFAULT_POMODORO_CONFIG, short_break_minutes=99)))
        self.assertIn("--cycles", validate_pomodoro_config(replace(DEFAULT_POMODORO_CONFIG, cycles_before_long_break=0)))


class GetPhaseDurationSecondsTest(unittest.TestCase):
    def test_maps_phases_to_seconds(self):
        self.assertEqual(get_phase_duration_seconds("focus", DEFAULT_POMODORO_CONFIG), 1500)
        self.assertEqual(get_phase_duration_seconds("shortBreak", DEFAULT_POMODORO_CONFIG), 300)
        self.assertEqual(get_phase_duration_seconds("longBreak", DEFAULT_POMODORO_CONFIG), 900)


class BuildSessionPlanTest(unittest.TestCase):
    def test_ends_with_long_break_after_n_focuses(self):
        plan = build_session_plan(DEFAULT_POMODORO_CONFIG, 2)
        self.assertEqual([item.phase for item in plan], ["focus", "shortBreak", "focus", "longBreak"])
        self.assertEqual(plan[0].focus_number, 1)
        self.assertEqual(plan[2].focus_number, 2)


class ParsePomodoroCliArgsTest(unittest.TestCase):
    def test_parses_flags_and_preset_override(self):
        result = parse_pomodoro_cli_args(["--pomodoro", "--preset", "sprint", "--focus", "20", "--query", "lofi"])
        self.assertTrue(result.enabled)
        self.assertEqual(result.config.focus_minutes, 20)  # explicit overrides preset
        self.assertEqual(result.config.short_break_minutes, 3)  # from sprint preset
        self.assertEqual(result.query, "lofi")
        self.assertIsNone(result.error)

    def test_reports_unknown_preset_and_invalid_durations(self):
        self.assertIn("Unknown --preset", parse_pomodoro_cli_args(["--pomodoro", "--preset", "nope"]).error)
        self.assertIn("--focus", parse_pomodoro_cli_args(["--pomodoro", "--focus", "0"]).error)

    def test_supports_equals_form_and_short_break_alias(self):
        result = parse_pomodoro_cli_args(["--pomodoro", "--focus=40", "--short-break", "7"])
        self.assertEqual(result.config.focus_minutes, 40)
        self.assertEqual(result.config.short_break_minutes, 7)
        self.assertIsNone(result.error)

    def test_flag_without_value_fails_validation(self):
        # The TypeScript parser yields "" for a valueless flag; Number("") is 0.
        self.assertIn("--focus", parse_pomodoro_cli_args(["--pomodoro", "--focus"]).error)


if __name__ == "__main__":
    unittest.main()
