# music-cli

A keyboard-first YouTube music player with Pomodoro focus sessions. Audio streams directly; nothing is downloaded.

## Features

- Search YouTube and select with arrow keys
- Stream audio on demand without local media files
- Start a Pomodoro session with focus music
- Neon ASCII banner, responsive now-playing panels, spinners, and live progress

## Prerequisites

You need to have these installed:

1. **Bun** - JavaScript runtime
   ```bash
   curl -fsSL https://bun.sh/install | bash
   ```

2. **FFmpeg** - For audio playback
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg` or `sudo dnf install ffmpeg`
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

3. **yt-dlp** - For YouTube streaming
   - macOS: `brew install yt-dlp`
   - Linux: `sudo apt install yt-dlp` or `pip install yt-dlp`
   - Windows: Download from [github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Setup

```bash
git clone https://github.com/testwiththeo/music-cli.git
cd music-cli
bun install
ln -sf "$PWD/index.ts" ~/.local/bin/music
```

The final command creates the `music` shortcut once. Restart your terminal if the command is not found.

## Usage

```bash
# Interactive search
music

# Search immediately
music "lofi hip hop"

# Pomodoro defaults: 25m focus, 5m break, 4 focuses
music --pomodoro --query "lofi hip hop"

# Quick one-minute smoke test
music --pomodoro --focus 1 --break 1 --cycles 1 --query "lofi hip hop"

# See every option
music --help
```

Set `NO_COLOR=1` to disable terminal colors.

## Pomodoro Controls

- `s`: skip the current phase
- `Esc`: stop music and keep the timer running
- `q` or `Ctrl+C`: quit the session

## Playback Controls

- `←`: seek back 5 seconds
- `→`: seek forward 5 seconds
- `Esc`: stop playback
- `Ctrl+C`: quit

## Development

Use these only when developing the project:

```bash
bun test
bun run typecheck
```

## Notes

- Audio streams directly from YouTube (no files saved)
- Requires active internet connection
- Uses `yt-dlp` CLI tool to get stream URLs
- Uses `ffplay` (part of FFmpeg) for audio playback
- Uses `yt-search` for YouTube search
