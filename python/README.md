# music-cli (Python port)

> Play music, not the recommendation feed.

A dependency-free Python translation of the TypeScript CLI in the repository
root — same features, same terminal UI, same keyboard model. The Python
version uses only the standard library; the heavy lifting is delegated to the
same external binaries the original already required: **yt-dlp** and
**ffmpeg/ffplay**.

## Requirements

- Python 3.9+
- [FFmpeg](https://ffmpeg.org/) with `ffplay`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

```bash
sudo apt install ffmpeg
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp
chmod +x ~/.local/bin/yt-dlp
```

## Install

```bash
cd python
pip install .            # installs the `music` command
```

Run without installing:

```bash
cd python
python3 -m music_cli "nujabes feather"
```

Note: this installs a second `music` entry point alongside the Bun symlink
from the TypeScript version — remove the old one
(`rm ~/.local/bin/music`) if you want this port to win.

## Usage

Identical to the original:

```bash
music                                    # interactive player
music "Nujabes modal soul"               # search immediately
music --pomodoro --query "lofi hip hop"  # 25/5 focus session with music
music --pomodoro --preset deep --query "jazz focus"
music --help
```

Keys (playback): ←/→ seek ±5s · Esc stop autoplay · Ctrl+C quit
Keys (pomodoro): s skip phase · Esc stop music only · q quit · Ctrl+C quit

## How it maps to the TypeScript original

| TypeScript | Python | Notes |
| --- | --- | --- |
| `index.ts` | `music_cli/cli.py` | main loop, playback engine, countdown, pomodoro runner |
| `src/pomodoro.ts` | `music_cli/pomodoro.py` | pure config / plan / flag parsing (JS `Number()` semantics preserved) |
| `src/recommendations.ts` | `music_cli/recommendations.py` | token-overlap autoplay scoring |
| `src/playback-controls.ts` | `music_cli/playback_controls.py` | arrow-key seek mapping |
| `src/ui.ts` | `music_cli/ui.py` | ANSI banner, cards, status lines, spinner, progress bar |
| `yt-search` (npm) | `music_cli/youtube.py` | search now runs through `yt-dlp ytsearch10:` — yt-dlp was already a runtime dependency |
| `@inquirer/prompts` (npm) | `music_cli/prompts.py` | raw-mode input + arrow-key select; Esc/Ctrl+C cancel into the same goodbye |
| `process.stdin.setRawMode` | `music_cli/terminal.py` | `termios` raw input; output processing kept so `\n` still expands to CRLF |
| `tests/*.test.ts` (bun) | `tests/test_*.py` (unittest) | also runnable under pytest |

### Deliberate differences

- **Search provider.** yt-dlp replaces the yt-search scraper, so there is one
  fewer package to break when YouTube changes its markup.
- **Ctrl+C during playback now quits.** The TypeScript help text promises
  this, but raw mode turns Ctrl+C into a plain byte (`0x03`) that the
  original ignored; the port honors the documented behavior.
- **ffplay gets `stdin=DEVNULL`.** The original inherited stdin, letting
  ffplay compete for keystrokes; the port guarantees keys reach the CLI.
- **Thread-safety.** Progress redraws and status prints share an output lock;
  player state (current time, process handles) is guarded, since the ticker,
  key reader, and process watcher are separate threads rather than one event
  loop.
- **Behavior quirks preserved:** pressing an arrow key during a Pomodoro
  countdown still stops the music (the original matches on the first byte,
  `27`), and an empty `--focus` flag still fails validation the same way.

## Personal radio

Autoplay is personalized by a local taste profile — Spotify's algorithm,
rebuilt for a terminal with no accounts and no telemetry:

- **Finished tracks** boost their artist; **Esc-stopped tracks** count as skips
  and demote theirs.
- Candidates get a small popularity boost and a duration-fit penalty, so a
  6-hour mix won't follow a 3-minute song.
- After three tracks by the same artist in a row, the radio deliberately
  varies artists.
- When the result pool runs dry, it re-seeds from your most-played artists.

The profile lives at `~/.local/share/music-cli/taste.json` (`Application
Support` on macOS, `%APPDATA%` on Windows), prunes stale low-signal entries,
and never leaves your machine.

## Development

```bash
cd python
python3 -m unittest discover -s tests -v   # or: pytest
```
