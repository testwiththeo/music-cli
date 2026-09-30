"""YouTube search and audio stream resolution through the yt-dlp binary.

Replaces the TypeScript dependency on the ``yt-search`` npm package: yt-dlp
is already required at runtime for stream resolution, so it doubles as the
search provider (``ytsearch10:``) — one fewer scraper to break. All process
launches avoid the shell.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class VideoInfo:
    """A search result — mirrors the yt-search video shape used by the CLI."""

    title: str
    video_id: str
    url: str
    duration_seconds: int
    duration_timestamp: str
    author_name: str
    view_count: int = 0


def format_duration(total_seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS (the shape yt-search timestamps had)."""
    s = max(0, int(total_seconds))
    hours, remainder = divmod(s, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_duration(timestamp: str) -> int:
    """Parse MM:SS / HH:MM:SS into seconds; 0 when the format is unknown."""
    parts = timestamp.split(":")
    try:
        if len(parts) == 2:
            mm, ss = float(parts[0]), float(parts[1])
            return int(mm * 60 + ss)
        if len(parts) == 3:
            hh, mm, ss = float(parts[0]), float(parts[1]), float(parts[2])
            return int(hh * 3600 + mm * 60 + ss)
    except ValueError:
        return 0
    return 0


def _yt_dlp(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["yt-dlp", *args], capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError("yt-dlp not found on PATH (install: https://github.com/yt-dlp/yt-dlp)") from error


def _last_stderr_line(stderr: str) -> str:
    lines = [line.strip() for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def search_youtube(query: str, limit: int = 10) -> list[VideoInfo]:
    """Search YouTube; raises RuntimeError when the lookup fails."""
    process = _yt_dlp(["--flat-playlist", "--dump-json", "--no-warnings", f"ytsearch{limit}:{query}"])
    if process.returncode != 0:
        detail = _last_stderr_line(process.stderr or "")
        raise RuntimeError(detail or f"yt-dlp search failed with code {process.returncode}")

    videos: list[VideoInfo] = []
    for line in process.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = entry.get("id") or ""
        if not video_id:
            continue
        duration = entry.get("duration")
        seconds = int(round(duration)) if isinstance(duration, (int, float)) else 0
        timestamp = "LIVE" if entry.get("is_live") else (format_duration(seconds) if seconds > 0 else "0:00")
        views = entry.get("view_count")
        videos.append(VideoInfo(
            title=entry.get("title") or "Unknown title",
            video_id=video_id,
            url=entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
            duration_seconds=seconds,
            duration_timestamp=timestamp,
            author_name=entry.get("channel") or entry.get("uploader") or "Unknown artist",
            view_count=int(views) if isinstance(views, (int, float)) else 0,
        ))
        if len(videos) >= limit:
            break
    return videos


def resolve_audio_url(video_url: str) -> str:
    """Resolve the bestaudio stream URL for a video (no shell involved)."""
    process = _yt_dlp(["-f", "bestaudio", "-g", video_url])
    url = ""
    for line in process.stdout.splitlines():
        line = line.strip()
        if line:
            url = line
            break
    if process.returncode == 0 and url:
        return url
    detail = (process.stderr or "").strip()
    raise RuntimeError(detail or "Could not resolve audio stream (try: yt-dlp -U)")
