const ESC = "\x1b[";
const useColor = process.stdout.isTTY === true && !process.env.NO_COLOR;

const color = (code: number, value: string) => useColor ? `${ESC}${code}m${value}${ESC}0m` : value;
const bold = (value: string) => color(1, value);
const dim = (value: string) => color(2, value);
const cyan = (value: string) => color(36, value);
const magenta = (value: string) => color(35, value);
const green = (value: string) => color(32, value);
const yellow = (value: string) => color(33, value);
const red = (value: string) => color(31, value);

function visibleLength(value: string): number {
  return value.replace(/\x1b\[[0-9;]*m/g, "").length;
}

function truncate(value: string, width: number): string {
  if (width < 4 || visibleLength(value) <= width) return value;
  return `${value.slice(0, Math.max(0, width - 3))}...`;
}

function terminalWidth(): number {
  return process.stdout.columns && process.stdout.columns >= 40 ? process.stdout.columns : 80;
}

const BANNER_ART = [
  "███╗   ███╗██╗   ██╗███████╗██╗ ██████╗  ██████╗██╗     ██╗",
  "████╗ ████║██║   ██║██╔════╝██║██╔════╝ ██╔════╝██║     ██║",
  "██╔████╔██║██║   ██║███████╗██║██║█████╗██║     ██║     ██║",
  "██║╚██╔╝██║██║   ██║╚════██║██║██║╚════╝██║     ██║     ██║",
  "██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗ ╚██████╗███████╗██║",
  "╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝  ╚═════╝╚══════╝╚═╝",
].join("\n");
const EQUALIZER = "▁▂▄▆█▆▄▂▁▂▄▇▆▄▂▁▂▅▇▅▂▁▂▄▆▄▂";
const TAGLINE = "terminal sound system · search / stream / focus";

export function printBanner(): void {
  if (!process.stdout.isTTY) {
    console.log("music-cli");
    return;
  }

  if ((process.stdout.columns ?? 80) < 64) {
    console.log(`${bold("♪ music-cli ")}${dim(TAGLINE)}`);
    return;
  }

  console.log(cyan(BANNER_ART));
  console.log(magenta("▶ ") + cyan(EQUALIZER));
  console.log(dim(TAGLINE) + "\n");
}

export function printCard(title: string, lines: string[]): void {
  const innerWidth = Math.max(36, Math.min(terminalWidth() - 4, 76));
  const border = cyan("─".repeat(innerWidth));
  console.log(`  ${cyan("╭")}${border}${cyan("╮")}`);
  const heading = bold(truncate(title, innerWidth - 2));
  console.log(`  ${cyan("│")} ${heading}${" ".repeat(Math.max(0, innerWidth - 1 - visibleLength(heading)))}${cyan("│")}`);
  for (const line of lines) {
    const text = truncate(line, innerWidth - 2);
    console.log(`  ${cyan("│")} ${text}${" ".repeat(Math.max(0, innerWidth - 1 - visibleLength(text)))}${cyan("│")}`);
  }
  console.log(`  ${cyan("╰")}${border}${cyan("╯")}`);
}

export function printStatus(kind: "info" | "success" | "warning" | "error", message: string): void {
  const styles = {
    info: ["◆", cyan],
    success: ["●", green],
    warning: ["▲", yellow],
    error: ["×", red],
  } as const;
  const [icon, paint] = styles[kind];
  console.log(`${paint(icon)} ${message}`);
}

export async function withSpinner<T>(label: string, operation: () => Promise<T>): Promise<T> {
  if (!process.stdout.isTTY) return operation();

  const frames = ["·", "✦", "✧", "✦"];
  let index = 0;
  const render = () => process.stdout.write(`\r${magenta(frames[index] ?? "·")} ${dim(label)}`);
  render();
  const timer = setInterval(() => {
    index = (index + 1) % frames.length;
    render();
  }, 110);

  try {
    return await operation();
  } finally {
    clearInterval(timer);
    process.stdout.write("\r\x1b[2K");
  }
}

export function renderProgress(current: number, total: number, label = "Elapsed"): void {
  const elapsed = formatTime(current);
  const totalLabel = total > 0 ? formatTime(total) : "--:--";
  const percentage = total > 0 ? Math.min(current / total, 1) : 0;
  const suffix = total > 0 ? ` ${Math.floor(percentage * 100)}%` : "";
  const available = terminalWidth() - visibleLength(`${label}  ${elapsed} / ${totalLabel}${suffix}`) - 8;
  const barWidth = Math.max(8, Math.min(32, available));
  const filled = total > 0 ? Math.floor(barWidth * percentage) : 0;
  const bar = `${green("━".repeat(filled))}${dim("━".repeat(barWidth - filled))}`;
  const pulse = ".:=#";
  const meter = Array.from({ length: 8 }, (_, index) => pulse[(current + index * 3) % pulse.length] ?? ".").join("");
  const line = `${magenta(label)} ${bar} ${bold(`${elapsed} / ${totalLabel}`)}${dim(suffix)} ${cyan(meter)}`;

  if (process.stdout.isTTY) process.stdout.write(`\r\x1b[2K${line}`);
  else if (current === 0 || current % 30 === 0) console.log(`${label} ${elapsed} / ${totalLabel}${suffix}`);
}

export function formatTime(seconds: number): string {
  const mins = Math.floor(Math.max(0, seconds) / 60);
  const secs = Math.floor(Math.max(0, seconds) % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export const ui = { bold, cyan, dim, green, magenta, yellow, red };
