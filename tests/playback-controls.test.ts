import { describe, expect, test } from "bun:test";
import { isEscapeKey, SEEK_SECONDS, seekOffsetForKey } from "../src/playback-controls";

describe("playback controls", () => {
  test("maps arrow keys to five-second seek offsets", () => {
    expect(seekOffsetForKey("\x1b[D")).toBe(-SEEK_SECONDS);
    expect(seekOffsetForKey("\x1b[C")).toBe(SEEK_SECONDS);
  });

  test("does not confuse arrow-key escape sequences with Escape", () => {
    expect(isEscapeKey(Buffer.from("\x1b"))).toBe(true);
    expect(isEscapeKey(Buffer.from("\x1b[D"))).toBe(false);
    expect(isEscapeKey(Buffer.from("\x1b[C"))).toBe(false);
  });
});
