"""Interactive entry point — Python port of the TypeScript ``index.ts``.

Search YouTube, stream the chosen track through ffplay, keep listening with
relevance-ranked autoplay, and run Pomodoro focus sessions. The playback
engine owns the keyboard in raw mode: ←/→ seek by killing and relaunching
ffplay at the desired offset (ffplay has no command API), Esc stops, Ctrl+C
quits.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Set, Tuple

from . import terminal
from . import youtube as youtube_search
from .playback_controls import is_escape_key, seek_offset_for_key
from .pomodoro import (
    PomodoroConfig,
    build_session_plan,
    format_countdown,
    parse_pomodoro_cli_args,
)
from . import __version__
from .prompts import PromptCancelled, prompt_input, prompt_select
from .recommendations import (
    RecommendationTrack,
    build_recommendation_query,
    pick_recommendation,
)
from .taste import TasteProfile, load_profile, record_play, record_skip
from .ui import (
    dim,
    print_banner,
    print_card,
    print_status,
    render_progress,
    ui,
    with_spinner,
)
from .youtube import VideoInfo, parse_duration, resolve_audio_url


def search_youtube(query: str) -> List[VideoInfo]:
    try:
        return with_spinner(f'Searching YouTube for "{query}"', lambda: youtube_search.search_youtube(query))
    except Exception as error:  # noqa: BLE001 — mirrors the TypeScript catch-all
        print_status("error", f"Search failed: {error}")
        return []


def as_recommendation_track(video: VideoInfo) -> RecommendationTrack:
    return RecommendationTrack(
        id=video.video_id,
        title=video.title,
        artist=video.author_name,
        view_count=video.view_count,
        duration_seconds=video.duration_seconds,
    )


def pick_video_recommendation(
    current: VideoInfo,
    candidates: List[VideoInfo],
    source_query: str,
    played_ids: Set[str],
    taste_profile: Optional[TasteProfile] = None,
    recent_artists: Sequence[str] = (),
) -> Optional[VideoInfo]:
    recommendation = pick_recommendation(
        as_recommendation_track(current),
        [as_recommendation_track(candidate) for candidate in candidates],
        source_query,
        played_ids,
        taste_profile,
        recent_artists,
    )
    if recommendation is None:
        return None
    for candidate in candidates:
        if candidate.video_id == recommendation.id:
            return candidate
    return None


def radio_seed_queries(
    current: VideoInfo,
    source_query: str,
    taste_profile: TasteProfile,
) -> List[Tuple[str, str]]:
    """Seed (query, label) pairs for pool expansion: artist + query first,
    then the listener's favorite artists from their taste profile
    (Spotify-style radio re-seeding, minus the server)."""
    seeds = [(build_recommendation_query(as_recommendation_track(current), source_query), current.author_name)]
    favorites = sorted(
        taste_profile.artists.items(),
        key=lambda item: (-item[1].plays, -item[1].last_played),
    )
    current_artist = current.author_name.strip().lower()
    for name, stats in favorites:
        if name == current_artist or stats.plays < 2:
            continue
        query = f"{name} {source_query} music" if source_query.strip() else f"{name} music"
        seeds.append((query, name))
        if len(seeds) >= 4:
            break
    return seeds


def print_now_playing(video: VideoInfo, autoplay: bool) -> None:
    print("")
    print_card("AUTOPLAY · FOR YOU" if autoplay else "NOW PLAYING", [
        ui.cyan(video.title),
        f"{video.author_name} · {video.duration_timestamp}",
    ])
    print("")


def draw_progress_bar(current: int, total: int) -> None:
    render_progress(current, total)


@dataclass
class PlayResult:
    stopped_by_user: bool


class _PlaybackSession:
    """Streams one track through ffplay while owning keyboard seek/stop."""

    def __init__(self, audio_url: str, total_seconds: int) -> None:
        self.audio_url = audio_url
        self.total_seconds = total_seconds
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._stop_threads = threading.Event()
        self._ffplay: Optional[subprocess.Popen] = None
        self._current_time = 0
        self._settled = False
        self._restarting = False
        self._cleaned_up = False
        self._raw_saved = terminal.enable_raw_mode()
        self._result = PlayResult(stopped_by_user=False)
        self._error: Optional[BaseException] = None

    def run(self) -> PlayResult:
        print_status("info", f"{dim('Controls')} ←/→ seek 5s · Esc stop · Ctrl+C quit")

        # Must run on the main thread for signal handling (like the original).
        previous_sigint = signal.signal(signal.SIGINT, self._on_sigint)
        if self._raw_saved is not None:
            threading.Thread(target=self._key_loop, daemon=True).start()
        threading.Thread(target=self._ticker, daemon=True).start()

        self._start_player()
        try:
            self._done.wait()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            self._cleanup()
        if self._error is not None:
            raise self._error
        return self._result

    # -- ffplay lifecycle --------------------------------------------------

    def _start_player(self) -> None:
        with self._lock:
            if self._settled or self._stop_threads.is_set():
                return
            existing = self._ffplay
            if existing is not None and existing.poll() is None:
                return  # a restart raced us and already relaunched
            offset = self._current_time
        try:
            process = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-ss", str(offset), self.audio_url],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            self._fail(error)
            return
        with self._lock:
            if self._settled:
                process.kill()
                return
            self._ffplay = process
        threading.Thread(target=self._watch_player, args=(process,), daemon=True).start()

    def _watch_player(self, process: subprocess.Popen) -> None:
        code = process.wait()
        with self._lock:
            if self._restarting or self._settled:
                return
            self._settled = True
        self._cleanup()
        if code == 0:
            print_status("success", "Playback finished")
            self._done.set()
        else:
            self._error = RuntimeError(f"ffplay exited with code {code}")
            self._done.set()

    def _restart_player(self) -> None:
        # ffplay has no command API. Restarting it at the desired offset is the
        # reliable way to seek while the CLI owns keyboard input in raw mode.
        with self._lock:
            process = self._ffplay
            if process is not None and process.poll() is None:
                self._restarting = True
            else:
                process = None
        if process is None:
            self._start_player()
            return

        def relaunch() -> None:
            process.wait()
            with self._lock:
                self._restarting = False
                settled = self._settled
            if not settled:
                self._start_player()

        threading.Thread(target=relaunch, daemon=True).start()
        process.kill()

    # -- input -------------------------------------------------------------

    def _key_loop(self) -> None:
        while not self._stop_threads.is_set():
            chunk = terminal.read_key_chunk(timeout=0.2)
            if chunk:
                self._handle_key(chunk)

    def _handle_key(self, chunk: bytes) -> None:
        seek_by = seek_offset_for_key(chunk)
        if seek_by is not None:
            with self._lock:
                if self.total_seconds > 0:
                    self._current_time = max(0, min(self.total_seconds, self._current_time + seek_by))
                else:
                    self._current_time = max(0, self._current_time + seek_by)
                current = self._current_time
            self._restart_player()
            draw_progress_bar(current, self.total_seconds)
            print_status("info", "Seek +5 seconds" if seek_by > 0 else "Seek -5 seconds")
            return

        # A plain Escape is one byte; arrow keys begin with Escape but are
        # handled above. Ctrl+C (0x03 — ISIG is off in raw mode) quits outright,
        # matching the documented controls and the SIGINT path.
        if is_escape_key(chunk) or chunk == b"\x03":
            print("")
            print_status("warning", "Playback stopped")
            self._finish(stopped_by_user=True)
            if chunk == b"\x03":
                os._exit(0)

    def _on_sigint(self, signum, frame) -> None:
        print("")
        print_status("warning", "Playback stopped")
        self._finish(stopped_by_user=True)
        os._exit(0)

    def _ticker(self) -> None:
        # Estimated progress; actual player position is not exposed by ffplay.
        while not self._stop_threads.wait(1.0):
            with self._lock:
                self._current_time += 1
                current = self._current_time
            if self.total_seconds == 0 or current <= self.total_seconds:
                draw_progress_bar(current, self.total_seconds)

    # -- shutdown ----------------------------------------------------------

    def _finish(self, stopped_by_user: bool) -> None:
        with self._lock:
            if self._settled:
                return
            self._settled = True
            process = self._ffplay
        if process is not None and process.poll() is None:
            process.kill()
        self._cleanup()
        self._result = PlayResult(stopped_by_user=stopped_by_user)
        self._done.set()

    def _fail(self, error: BaseException) -> None:
        with self._lock:
            if self._settled:
                return
            self._settled = True
            process = self._ffplay
        if process is not None and process.poll() is None:
            process.kill()
        self._cleanup()
        self._error = error
        self._done.set()

    def _cleanup(self) -> None:
        with self._lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True
        self._stop_threads.set()
        terminal.restore_raw_mode(self._raw_saved)
        sys.stdout.write("\n")  # move to a new line after the progress bar
        sys.stdout.flush()


def play_audio(video: VideoInfo) -> PlayResult:
    try:
        audio_url = with_spinner("Resolving audio stream", lambda: resolve_audio_url(video.url))
        if not audio_url:
            raise RuntimeError("Could not get audio stream URL")
        total_seconds = video.duration_seconds or parse_duration(video.duration_timestamp)
    except Exception as error:  # noqa: BLE001 — reported, then re-raised like the original
        print_status("error", f"Playback failed: {error}")
        raise
    return _PlaybackSession(audio_url, total_seconds).run()


@dataclass
class PhaseControl:
    skipped: bool = False
    quit: bool = False
    music_stopped: bool = False


def countdown_with_keys(
    total_seconds: int,
    label: str,
    on_music_stop: Optional[Callable[[], None]] = None,
) -> PhaseControl:
    """Countdown timer with raw-mode keys: s skip · Esc stop music · q quit."""
    ctrl = PhaseControl()
    remaining = total_seconds
    finished = threading.Event()
    key_events: "queue.Queue[bytes]" = queue.Queue()
    stop_reader = threading.Event()
    use_raw = sys.stdin.isatty()
    raw_saved = terminal.enable_raw_mode() if use_raw else None
    cleaned_up = threading.Event()

    def render() -> None:
        render_progress(total_seconds - remaining, total_seconds, label)

    def cleanup() -> None:
        if cleaned_up.is_set():
            return
        cleaned_up.set()
        stop_reader.set()
        terminal.restore_raw_mode(raw_saved)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def on_sigint(signum, frame) -> None:
        key_events.put(b"\x03")

    def reader() -> None:
        while not stop_reader.is_set():
            chunk = terminal.read_key_chunk(timeout=0.2)
            if chunk:
                key_events.put(chunk)

    if use_raw:
        threading.Thread(target=reader, daemon=True).start()
    previous_sigint = signal.signal(signal.SIGINT, on_sigint)

    render()
    while not finished.is_set():
        try:
            chunk = key_events.get(timeout=1.0)
        except queue.Empty:
            remaining -= 1
            if remaining <= 0:
                break
            render()
            continue

        key = chunk[0]
        if key == 27:
            # First-byte check, exactly like the original: arrow keys also
            # land here and stop the music while the timer keeps running.
            if not ctrl.music_stopped:
                ctrl.music_stopped = True
                if on_music_stop is not None:
                    on_music_stop()
                sys.stdout.write("\n")
                print_status("warning", "Music stopped · timer continues")
        elif key in (115, 83):  # s / S
            ctrl.skipped = True
            finished.set()
        elif key in (113, 81, 3):  # q / Q / Ctrl+C
            ctrl.quit = True
            finished.set()

    cleanup()
    signal.signal(signal.SIGINT, previous_sigint)
    return ctrl


def run_pomodoro_session(
    config: PomodoroConfig,
    focus_query: Optional[str] = None,
    break_query: Optional[str] = None,
) -> None:
    # Validation guarantees a whole number; JS templates rendered it without decimals.
    total_focuses = int(config.cycles_before_long_break)
    plan = build_session_plan(config)
    print("")
    print_card("POMODORO SESSION", [
        f"Focus  {config.focus_minutes:g} min × {total_focuses}",
        f"Break  {config.short_break_minutes:g} min · Long {config.long_break_minutes:g} min",
        dim("s skip phase · Esc stop music · q quit"),
    ])
    print("")

    focus_search_cache: Optional[List[VideoInfo]] = None
    if focus_query:
        print_status("info", f'Finding focus music: "{focus_query}"')
        focus_search_cache = search_youtube(focus_query)
        if not focus_search_cache:
            print_status("warning", "No focus music found · timer will run silent")
        else:
            first = focus_search_cache[0] if focus_search_cache else None
            print_status("success", f"Focus track ready: {first.title if first else 'unknown'}")

    completed_focuses = 0
    started_at = time.time()

    for item in plan:
        is_focus = item.phase == "focus"
        music_query = focus_query if is_focus else break_query
        cache = focus_search_cache if is_focus else None
        icon = "FOCUS" if is_focus else "BREAK"
        print("")
        print_card(f"{icon} · {item.label.upper()}", [
            f"{format_countdown(item.duration_seconds)} remaining",
            dim("Lock in. Your music starts below." if is_focus else "Step away. Breathe. Reset."),
        ])
        print("")

        # Start music for this phase (best-effort, shell-free).
        ffplay: Optional[subprocess.Popen] = None
        try:
            track: Optional[VideoInfo] = None
            if music_query and is_focus and cache:
                track = cache[min(completed_focuses, len(cache) - 1)]
            elif music_query and not is_focus:
                results = search_youtube(music_query)
                track = results[0] if results else None
            if track is not None:
                stream_url = resolve_audio_url(track.url)
                ffplay = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", stream_url],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print_status("success", f"Playing: {track.title}")
        except Exception as error:  # noqa: BLE001 — music is best-effort
            print_status("warning", f"Music skipped: {error}")

        def stop_music() -> None:
            nonlocal ffplay
            if ffplay is not None and ffplay.poll() is None:
                ffplay.kill()
            ffplay = None

        ctrl = countdown_with_keys(item.duration_seconds, f"{icon} {item.label}", stop_music)
        stop_music()

        if ctrl.quit:
            print_status("warning", "Pomodoro quit")
            break
        if is_focus and not ctrl.skipped:
            completed_focuses += 1
        sys.stdout.write("\x07")  # bell
        sys.stdout.flush()
        print_status(
            "warning" if ctrl.skipped else "success",
            "Phase skipped" if ctrl.skipped else ("Focus done · take a break" if is_focus else "Break over · back to focus"),
        )

    minutes = int((time.time() - started_at) / 60 + 0.5)
    print("")
    print_card("SESSION COMPLETE", [
        f"{completed_focuses}/{total_focuses} focus blocks completed",
        f"~{minutes} minutes elapsed",
    ])
    print("")


def print_help() -> None:
    print("""🎵 music-cli — YouTube Music Player + Pomodoro

Usage:
  music [query...]                       Search and play
  music --pomodoro [options]             Start a Pomodoro focus session
  music --help | music --version

Pomodoro options:
  --focus <min>        Focus length (1-180, default 25)
  --break <min>        Short break (1-60, default 5, alias --short-break)
  --long-break <min>   Long break (1-90, default 15)
  --cycles <n>         Focuses before long break (1-12, default 4)
  --preset <name>      classic|deep|sprint (explicit flags override preset)
  --query "<q>"        Focus music search (top result auto-plays per focus)
  --break-query "<q>"  Optional music for breaks (default: silence)

Keys (pomodoro): s skip phase · Esc stop music only · q quit · Ctrl+C quit
Keys (playback): ←/→ seek 5s · Esc stop autoplay · Ctrl+C quit

Examples:
  music --pomodoro --query "lofi hip hop"
  music --pomodoro --preset deep --query "jazz focus"
  music "synthwave"
""")


def main() -> None:
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print_help()
        sys.exit(0)
    if "--version" in argv or "-V" in argv:
        print(f"music-cli v{__version__}")
        sys.exit(0)

    pomo = parse_pomodoro_cli_args(argv)
    if pomo.enabled:
        if pomo.error:
            print(f"❌ {pomo.error}", file=sys.stderr)
            sys.exit(2)
        # Positional query fallback: `music --pomodoro lofi` (any non-flag args).
        positional = [a for a in argv if not a.startswith("--") and a != pomo.query and a != pomo.break_query]
        focus_query = pomo.query if pomo.query is not None else (" ".join(positional) if positional else None)
        run_pomodoro_session(pomo.config, focus_query or None, pomo.break_query or None)
        sys.exit(0)

    # Positional query shortcut: `music lofi hip hop` → skip first prompt once.
    positional_query = " ".join(a for a in argv if not a.startswith("-")).strip()
    initial_query: Optional[str] = positional_query or None

    taste = load_profile()
    print_banner()

    while True:
        try:
            # Get search query from user (or use positional `music lofi hip hop` once)
            if initial_query:
                query = initial_query
                initial_query = None
                print_status("info", f'Search: "{query}"')
            else:
                query = prompt_input("Search for music (ESC to exit):")

            if not query.strip():
                print("Please enter a search query\n")
                continue

            print("")

            # Search YouTube
            results = search_youtube(query)
            if not results:
                print_status("warning", f'No results for "{query}" · try artist + song')
                print("")
                continue

            # Keep showing the same results until user finishes a song naturally
            continue_with_same_results = True
            while continue_with_same_results:
                choices: List[Tuple[str, object]] = [("←  Search again", None)]
                choices += [
                    (
                        f"{ui.cyan('›')} {video.title} {ui.dim(f'— {video.author_name} · {video.duration_timestamp}')}",
                        video,
                    )
                    for video in results
                ]
                selected_video = prompt_select('Select a track (or choose "Search again"):', choices)

                # If user chose to search again
                if selected_video is None:
                    print("")
                    print_status("info", "New search")
                    print("")
                    break

                current_video: VideoInfo = selected_video
                recommendation_pool = results
                played_ids: Set[str] = set()
                recent_artists: List[str] = []
                autoplay = False

                while True:
                    print_now_playing(current_video, autoplay)
                    played_ids.add(current_video.video_id)

                    outcome = play_audio(current_video)
                    if outcome.stopped_by_user:
                        # Escape is an intentional stop: count it as a skip in the
                        # taste profile, then return to the user's current results.
                        record_skip(taste, as_recommendation_track(current_video))
                        save_profile(taste)
                        continue_with_same_results = True
                        break

                    record_play(taste, as_recommendation_track(current_video), query)
                    save_profile(taste)
                    recent_artists.append(current_video.author_name)

                    next_video = pick_video_recommendation(
                        current_video, recommendation_pool, query, played_ids, taste, recent_artists,
                    )
                    if next_video is None:
                        # Expand the pool: artist + query first, then radio seeds
                        # drawn from the listener's favorite artists.
                        for seed_query, seed_label in radio_seed_queries(current_video, query, taste):
                            print_status("info", f"Finding more like {seed_label}")
                            recommendation_pool = search_youtube(seed_query)
                            next_video = pick_video_recommendation(
                                current_video, recommendation_pool, query, played_ids, taste, recent_artists,
                            )
                            if next_video is not None:
                                break

                    if next_video is None:
                        print_status("warning", "No new recommendation found · start another search")
                        continue_with_same_results = False
                        break

                    print_status("success", f"Up next: {next_video.title} — {next_video.author_name}")
                    current_video = next_video
                    autoplay = True

        except (PromptCancelled, KeyboardInterrupt):
            # Prompts cancel the same way inquirer's exit error did.
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        except Exception as error:  # noqa: BLE001 — keep the session alive
            print(f"Error: {error}", file=sys.stderr)
            print("\n")
