export type PomodoroPhase = "focus" | "shortBreak" | "longBreak";

export interface PomodoroConfig {
  focusMinutes: number;
  shortBreakMinutes: number;
  longBreakMinutes: number;
  cyclesBeforeLongBreak: number;
}

export interface PomodoroPlanItem {
  phase: PomodoroPhase;
  focusNumber: number; // 1-based, which focus this item belongs to / follows
  durationSeconds: number;
  label: string;
}

export const DEFAULT_POMODORO_CONFIG: PomodoroConfig = {
  focusMinutes: 25,
  shortBreakMinutes: 5,
  longBreakMinutes: 15,
  cyclesBeforeLongBreak: 4,
};

export const POMODORO_PRESETS: Record<string, PomodoroConfig> = {
  classic: { focusMinutes: 25, shortBreakMinutes: 5, longBreakMinutes: 15, cyclesBeforeLongBreak: 4 },
  deep: { focusMinutes: 50, shortBreakMinutes: 10, longBreakMinutes: 30, cyclesBeforeLongBreak: 2 },
  sprint: { focusMinutes: 15, shortBreakMinutes: 3, longBreakMinutes: 10, cyclesBeforeLongBreak: 4 },
};

export function validatePomodoroConfig(config: PomodoroConfig): string | null {
  if (!Number.isFinite(config.focusMinutes) || config.focusMinutes < 1 || config.focusMinutes > 180) {
    return "Invalid --focus: expected 1-180 minutes.";
  }
  if (!Number.isFinite(config.shortBreakMinutes) || config.shortBreakMinutes < 1 || config.shortBreakMinutes > 60) {
    return "Invalid --break: expected 1-60 minutes.";
  }
  if (!Number.isFinite(config.longBreakMinutes) || config.longBreakMinutes < 1 || config.longBreakMinutes > 90) {
    return "Invalid --long-break: expected 1-90 minutes.";
  }
  if (
    !Number.isInteger(config.cyclesBeforeLongBreak) ||
    config.cyclesBeforeLongBreak < 1 ||
    config.cyclesBeforeLongBreak > 12
  ) {
    return "Invalid --cycles: expected integer 1-12.";
  }
  return null;
}

export function getPhaseDurationSeconds(phase: PomodoroPhase, config: PomodoroConfig): number {
  switch (phase) {
    case "focus":
      return Math.round(config.focusMinutes * 60);
    case "shortBreak":
      return Math.round(config.shortBreakMinutes * 60);
    case "longBreak":
      return Math.round(config.longBreakMinutes * 60);
  }
}

export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function phaseLabel(phase: PomodoroPhase, focusNumber: number, totalCycles: number): string {
  switch (phase) {
    case "focus":
      return `Focus ${focusNumber}/${totalCycles}`;
    case "shortBreak":
      return `Short break after focus ${focusNumber}`;
    case "longBreak":
      return `Long break`;
  }
}

/** Build a full session plan: focus, break, focus, break … ending with a long break. */
export function buildSessionPlan(config: PomodoroConfig, totalFocuses?: number): PomodoroPlanItem[] {
  const n = totalFocuses ?? config.cyclesBeforeLongBreak;
  const plan: PomodoroPlanItem[] = [];
  for (let i = 1; i <= n; i++) {
    plan.push({
      phase: "focus",
      focusNumber: i,
      durationSeconds: getPhaseDurationSeconds("focus", config),
      label: phaseLabel("focus", i, n),
    });
    if (i < n) {
      plan.push({
        phase: "shortBreak",
        focusNumber: i,
        durationSeconds: getPhaseDurationSeconds("shortBreak", config),
        label: phaseLabel("shortBreak", i, n),
      });
    } else {
      plan.push({
        phase: "longBreak",
        focusNumber: i,
        durationSeconds: getPhaseDurationSeconds("longBreak", config),
        label: phaseLabel("longBreak", i, n),
      });
    }
  }
  return plan;
}

export interface ParsedPomodoroCli {
  enabled: boolean;
  config: PomodoroConfig;
  query?: string;
  breakQuery?: string;
  error?: string;
}

/** Minimal flag parser for pomodoro-related args. Pure + testable. */
export function parsePomodoroCliArgs(argv: string[]): ParsedPomodoroCli {
  const enabled = argv.includes("--pomodoro");
  let config: PomodoroConfig = { ...DEFAULT_POMODORO_CONFIG };
  let query: string | undefined;
  let breakQuery: string | undefined;

  const takeValue = (names: string[]): string | undefined => {
    for (const name of names) {
      const idx = argv.indexOf(name);
      if (idx !== -1) {
        const v = argv[idx + 1];
        if (v === undefined || v.startsWith("--")) return "";
        return v;
      }
      const prefixed = argv.find((a) => a.startsWith(`${name}=`));
      if (prefixed) return prefixed.slice(name.length + 1);
    }
    return undefined;
  };

  const presetName = takeValue(["--preset"]);
  if (presetName !== undefined) {
    const preset = POMODORO_PRESETS[presetName];
    if (!preset) {
      return { enabled, config, error: `Unknown --preset "${presetName}". Try classic|deep|sprint.` };
    }
    config = { ...preset };
  }

  const focusRaw = takeValue(["--focus"]);
  const breakRaw = takeValue(["--break", "--short-break"]);
  const longRaw = takeValue(["--long-break"]);
  const cyclesRaw = takeValue(["--cycles"]);
  const queryRaw = takeValue(["--query"]);
  const breakQueryRaw = takeValue(["--break-query"]);

  if (focusRaw !== undefined) config.focusMinutes = Number(focusRaw);
  if (breakRaw !== undefined) config.shortBreakMinutes = Number(breakRaw);
  if (longRaw !== undefined) config.longBreakMinutes = Number(longRaw);
  if (cyclesRaw !== undefined) config.cyclesBeforeLongBreak = Number(cyclesRaw);
  if (queryRaw !== undefined) query = queryRaw;
  if (breakQueryRaw !== undefined) breakQuery = breakQueryRaw;

  if (enabled) {
    const err = validatePomodoroConfig(config);
    if (err) return { enabled, config, query, breakQuery, error: err };
  }
  return { enabled, config, query, breakQuery };
}
