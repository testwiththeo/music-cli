# music-cli

> Play music, not the recommendation feed.

YouTube, Spotify, and other music platforms are too distracting. One search
becomes thumbnails, comments, Shorts, and autoplay — and another 20 minutes
gone. `music-cli` keeps the useful part: search for a track, stream it in your
terminal, and keep your attention where it belongs.

It is a keyboard-first music player with a built-in Pomodoro mode for focused
work sessions. No browser tab. No downloads. No recommendation rabbit hole.

```text
███╗   ███╗██╗   ██╗███████╗██╗ ██████╗  ██████╗██╗     ██╗
████╗ ████║██║   ██║██╔════╝██║██╔════╝ ██╔════╝██║     ██║
██╔████╔██║██║   ██║███████╗██║██║█████╗██║     ██║     ██║
██║╚██╔╝██║██║   ██║╚════██║██║██║╚════╝██║     ██║     ██║
██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗ ╚██████╗███████╗██║
╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝  ╚═════╝╚══════╝╚═╝
▶ ▁▂▄▆█▆▄▂▁▂▄▇▆▄▂▁▂▅▇▅▂▁▂▄▆▄▂
  terminal sound system · search / stream / focus
```

## Why?

Browser music is built to maximize watch time, not focus. `music-cli` is for
developers and terminal people who want background music without inviting an
algorithm into their workflow.

- Search and choose tracks with the keyboard.
- Stream audio directly, without saving media files.
- Run 25/5 Pomodoro sessions with optional focus music.
- Get a responsive terminal UI with status cards, spinners, and live progress.
- Keep listening with relevance-ranked autoplay after each completed track.
- Keep it local: no account, cookies, history sync, or browser session.

## Quick Start

### Prerequisites

- [Bun](https://bun.sh)
- [FFmpeg](https://ffmpeg.org/) with `ffplay`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

On Ubuntu/Debian:

```bash
sudo apt install ffmpeg
curl -fsSL https://bun.sh/install | bash
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp
chmod +x ~/.local/bin/yt-dlp
```

### Install

```bash
git clone https://github.com/testwiththeo/music-cli.git
cd music-cli
bun install
ln -sf "$PWD/index.ts" ~/.local/bin/music
```

The final command creates `music` as a one-time shortcut. Restart your terminal
if `music` is not found.

## Usage

```bash
# Open the interactive player
music

# Search immediately
music "Nujabes modal soul"

# When a track finishes, music-cli automatically plays an unplayed, relevant track.
# Press Esc at any time to stop autoplay and return to the result list.

# Start a 25/5 focus session with music
music --pomodoro --query "lofi hip hop"

# Try a one-minute focus session
music --pomodoro --focus 1 --break 1 --cycles 1 --query "jazz focus"

# See all options
music --help
```

Set `NO_COLOR=1` to run without terminal colors.

## Controls

| Context | Key | Action |
| --- | --- | --- |
| Playback | `←` / `→` | Seek backward / forward 5 seconds |
| Playback | `Esc` | Stop playback |
| Playback | `Ctrl+C` | Quit |
| Pomodoro | `s` | Skip the current phase |
| Pomodoro | `Esc` | Stop music and keep the timer running |
| Pomodoro | `q` / `Ctrl+C` | Quit the session |

## How It Works

1. `yt-search` finds matching YouTube videos.
2. `yt-dlp` resolves a fresh audio stream only when a track starts.
3. `ffplay` plays the stream directly.
4. Arrow-key seeking restarts `ffplay` at the requested offset, which keeps the
   terminal in control of keyboard input.
5. After a track completes, candidates are ranked by artist, title, and the
   original search. Played tracks are excluded. When the original results are
   exhausted, a fresh artist-and-query search expands the radio. The Python
   port adds a local taste profile: plays and skips per artist shape the
   ranking, and the radio re-seeds from your most-played artists.

No audio URLs are stored. No media files are downloaded.

## Limitations

- An internet connection and a working audio device are required.
- Playback depends on YouTube, `yt-dlp`, and `ffplay`; provider changes can
  affect availability.
- This project is not affiliated with YouTube or Google.
- Use it responsibly and in accordance with the terms that apply to the media
  you access.

## Development

```bash
bun test
bun run typecheck
```

## Python port

A dependency-free Python translation of this CLI lives in
[`python/`](./python) — same features and controls, driven by yt-dlp and
ffmpeg, with no npm packages (yt-dlp doubles as the search provider). See
[`python/README.md`](./python/README.md) for install instructions and the
full TypeScript → Python module mapping.
