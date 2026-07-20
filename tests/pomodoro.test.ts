import { describe, test, expect } from "bun:test";
import {
  buildSessionPlan,
  formatCountdown,
  getPhaseDurationSeconds,
  parsePomodoroCliArgs,
  validatePomodoroConfig,
  DEFAULT_POMODORO_CONFIG,
} from "../src/pomodoro";

describe("formatCountdown", () => {
  test("formats minutes and seconds", () => {
    expect(formatCountdown(25 * 60)).toBe("25:00");
    expect(formatCountdown(59)).toBe("0:59");
    expect(formatCountdown(0)).toBe("0:00");
    expect(formatCountdown(-5)).toBe("0:00");
  });
});

describe("validatePomodoroConfig", () => {
  test("accepts defaults", () => {
    expect(validatePomodoroConfig(DEFAULT_POMODORO_CONFIG)).toBeNull();
  });

  test("rejects out-of-range durations", () => {
    expect(validatePomodoroConfig({ ...DEFAULT_POMODORO_CONFIG, focusMinutes: 0 })).toContain("--focus");
    expect(validatePomodoroConfig({ ...DEFAULT_POMODORO_CONFIG, shortBreakMinutes: 99 })).toContain("--break");
    expect(
      validatePomodoroConfig({ ...DEFAULT_POMODORO_CONFIG, cyclesBeforeLongBreak: 0 }),
    ).toContain("--cycles");
  });
});

describe("getPhaseDurationSeconds", () => {
  test("maps phases to seconds", () => {
    expect(getPhaseDurationSeconds("focus", DEFAULT_POMODORO_CONFIG)).toBe(1500);
    expect(getPhaseDurationSeconds("shortBreak", DEFAULT_POMODORO_CONFIG)).toBe(300);
    expect(getPhaseDurationSeconds("longBreak", DEFAULT_POMODORO_CONFIG)).toBe(900);
  });
});

describe("buildSessionPlan", () => {
  test("ends with long break after N focuses", () => {
    const plan = buildSessionPlan(DEFAULT_POMODORO_CONFIG, 2);
    expect(plan.map((p) => p.phase)).toEqual(["focus", "shortBreak", "focus", "longBreak"]);
    expect(plan[0]?.focusNumber).toBe(1);
    expect(plan[2]?.focusNumber).toBe(2);
  });
});

describe("parsePomodoroCliArgs", () => {
  test("parses flags and preset override", () => {
    const r = parsePomodoroCliArgs(["--pomodoro", "--preset", "sprint", "--focus", "20", "--query", "lofi"]);
    expect(r.enabled).toBe(true);
    expect(r.config.focusMinutes).toBe(20); // explicit overrides preset
    expect(r.config.shortBreakMinutes).toBe(3); // from sprint preset
    expect(r.query).toBe("lofi");
    expect(r.error).toBeUndefined();
  });

  test("reports unknown preset and invalid durations", () => {
    expect(parsePomodoroCliArgs(["--pomodoro", "--preset", "nope"]).error).toContain("Unknown --preset");
    expect(parsePomodoroCliArgs(["--pomodoro", "--focus", "0"]).error).toContain("--focus");
  });
});
