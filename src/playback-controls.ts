export const SEEK_SECONDS = 5;

export function seekOffsetForKey(key: string): number | null {
  if (key === "\x1b[C") return SEEK_SECONDS;
  if (key === "\x1b[D") return -SEEK_SECONDS;
  return null;
}

export function isEscapeKey(key: Buffer): boolean {
  return key.length === 1 && key[0] === 27;
}
