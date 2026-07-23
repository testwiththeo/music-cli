#!/usr/bin/env bun

import { input, select } from '@inquirer/prompts';
import ytSearch from 'yt-search';
import { spawn } from 'child_process';
import { promisify } from 'util';
import { exec as execCallback } from 'child_process';
import {
  buildSessionPlan,
  formatCountdown,
  parsePomodoroCliArgs,
  type PomodoroConfig,
} from './src/pomodoro';
import {
  formatTime,
  printBanner,
  printCard,
  printStatus,
  renderProgress,
  ui,
  withSpinner,
} from './src/ui';
import { isEscapeKey, seekOffsetForKey } from './src/playback-controls';

const exec = promisify(execCallback);

interface VideoInfo {
  title: string;
  videoId: string;
  url: string;
  duration: {
    timestamp: string;
  };
  author: {
    name: string;
  };
}

async function searchYouTube(query: string): Promise<VideoInfo[]> {
  try {
    const result = await withSpinner(`Searching YouTube for "${query}"`, () => ytSearch(query));
    return result.videos.slice(0, 10);
  } catch (error) {
    printStatus('error', `Search failed: ${error instanceof Error ? error.message : error}`);
    return [];
  }
}

function parseDuration(timestamp: string): number {
  const parts = timestamp.split(':').map(Number);
  if (parts.length === 2) {
    // Format: MM:SS
    const [mm, ss] = parts;
    if (mm === undefined || ss === undefined || Number.isNaN(mm) || Number.isNaN(ss)) return 0;
    return mm * 60 + ss;
  } else if (parts.length === 3) {
    // Format: HH:MM:SS
    const [hh, mm, ss] = parts;
    if (hh === undefined || mm === undefined || ss === undefined) return 0;
    if (Number.isNaN(hh) || Number.isNaN(mm) || Number.isNaN(ss)) return 0;
    return hh * 3600 + mm * 60 + ss;
  }
  return 0;
}

function drawProgressBar(current: number, total: number) {
  renderProgress(current, total);
}

async function playAudio(videoUrl: string, duration: string): Promise<{ stoppedByUser: boolean }> {
  try {
    // Use yt-dlp to get the best audio stream URL
    const { stdout } = await withSpinner('Resolving audio stream', () => exec(`yt-dlp -f bestaudio -g "${videoUrl}"`));
    const audioUrl = stdout.trim();

    if (!audioUrl) {
      throw new Error('Could not get audio stream URL');
    }

    const totalSeconds = parseDuration(duration);

    return new Promise<{ stoppedByUser: boolean }>((resolve, reject) => {
      printStatus('info', `${ui.dim('Controls')} ←/→ seek 5s · Esc stop · Ctrl+C quit`);

      let currentTime = 0;
      let ffplay: ReturnType<typeof spawn> | null = null;
      let progressInterval: ReturnType<typeof setInterval> | undefined;
      let settled = false;
      let restarting = false;
      let cleanedUp = false;

      const cleanup = () => {
        if (cleanedUp) return;
        cleanedUp = true;
        if (progressInterval) clearInterval(progressInterval);
        if (process.stdin.isTTY) {
          process.stdin.setRawMode(false);
          process.stdin.pause();
        }
        process.stdin.removeListener('data', keyHandler);
        process.removeListener('SIGINT', sigintHandler);
        process.stdout.write('\n'); // Move to new line after progress bar
      };

      const finish = (stoppedByUser: boolean) => {
        if (settled) return;
        settled = true;
        ffplay?.kill();
        cleanup();
        resolve({ stoppedByUser });
      };

      const startPlayer = () => {
        // ffplay has no command API. Restarting it at the desired offset is the
        // reliable way to seek while the CLI owns keyboard input in raw mode.
        ffplay = spawn('ffplay', [
          '-nodisp',
          '-autoexit',
          '-loglevel', 'quiet',
          '-ss', String(currentTime),
          audioUrl,
        ]);

        ffplay.on('close', (code) => {
          if (restarting || settled) return;
          cleanup();
          if (code === 0) {
            settled = true;
            printStatus('success', 'Playback finished');
            resolve({ stoppedByUser: false });
          } else if (code !== null) {
            settled = true;
            reject(new Error(`ffplay exited with code ${code}`));
          }
        });

        ffplay.on('error', (error) => {
          if (restarting || settled) return;
          settled = true;
          cleanup();
          reject(error);
        });
      };

      const restartAtCurrentTime = () => {
        const activePlayer = ffplay;
        if (!activePlayer || activePlayer.killed) {
          startPlayer();
          return;
        }

        restarting = true;
        activePlayer.once('close', () => {
          restarting = false;
          if (!settled) startPlayer();
        });
        activePlayer.kill();
      };

      const keyHandler = (data: Buffer) => {
        const key = data.toString();
        const seekBy = seekOffsetForKey(key);

        if (seekBy !== null) {
          currentTime = totalSeconds > 0
            ? Math.max(0, Math.min(totalSeconds, currentTime + seekBy))
            : Math.max(0, currentTime + seekBy);
          restartAtCurrentTime();
          drawProgressBar(currentTime, totalSeconds);
          printStatus('info', seekBy > 0 ? 'Seek +5 seconds' : 'Seek -5 seconds');
          return;
        }

        // A plain Escape is one byte. Arrow keys begin with Escape but are handled above.
        if (isEscapeKey(data)) {
          console.log('');
          printStatus('warning', 'Playback stopped');
          finish(true);
        }
      };

      const sigintHandler = () => {
        console.log('');
        printStatus('warning', 'Playback stopped');
        finish(true);
        process.exit(0);
      };

      startPlayer();

      // Enable raw mode to capture controls after ffplay starts.
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(true);
        process.stdin.resume();
      }

      // Listen for key presses
      process.stdin.on('data', keyHandler);

      // Handle Ctrl+C
      process.on('SIGINT', sigintHandler);

      // Estimated progress; actual player position is not exposed by ffplay.
      progressInterval = setInterval(() => {
        currentTime++;
        if (totalSeconds === 0 || currentTime <= totalSeconds) {
          drawProgressBar(currentTime, totalSeconds);
        }
      }, 1000);
    });
  } catch (error) {
    printStatus('error', `Playback failed: ${error instanceof Error ? error.message : error}`);
    throw error;
  }
}

function printHelp() {
  console.log(`🎵 music-cli — YouTube Music Player + Pomodoro

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
Keys (playback): ←/→ seek 5s · Esc stop · Ctrl+C quit

Examples:
  music --pomodoro --query "lofi hip hop"
  music --pomodoro --preset deep --query "jazz focus"
  music "synthwave"
`);
}

function resolveAudioUrlNoShell(videoUrl: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn('yt-dlp', ['-f', 'bestaudio', '-g', videoUrl], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => (out += d.toString()));
    child.stderr.on('data', (d) => (err += d.toString()));
    child.on('error', reject);
    child.on('close', (code) => {
      const url = out.trim().split('\n')[0]?.trim() ?? '';
      if (code === 0 && url) resolve(url);
      else reject(new Error(err.trim() || 'Could not resolve audio stream (try: yt-dlp -U)'));
    });
  });
}

type PhaseControl = { skipped: boolean; quit: boolean; musicStopped: boolean };

function countdownWithKeys(
  totalSeconds: number,
  label: string,
  onMusicStop?: () => void,
): Promise<PhaseControl> {
  return new Promise((resolve) => {
    let remaining = totalSeconds;
    const ctrl: PhaseControl = { skipped: false, quit: false, musicStopped: false };
    const render = () => {
      renderProgress(totalSeconds - remaining, totalSeconds, label);
    };

    const useRaw = process.stdin.isTTY === true;
    const onData = (data: Buffer) => {
      const b = data[0] ?? -1;
      if (b === 27) {
        if (!ctrl.musicStopped) {
          ctrl.musicStopped = true;
          onMusicStop?.();
          process.stdout.write('\n');
          printStatus('warning', 'Music stopped · timer continues');
        }
      } else if (b === 115 || b === 83) {
        cleanup();
        ctrl.skipped = true;
        resolve(ctrl);
      } else if (b === 113 || b === 81 || b === 3) {
        cleanup();
        ctrl.quit = true;
        resolve(ctrl);
      }
    };
    const onSigint = () => {
      cleanup();
      ctrl.quit = true;
      resolve(ctrl);
    };

    const cleanup = () => {
      clearInterval(timer);
      if (useRaw) {
        try { process.stdin.setRawMode(false); } catch { /* noop */ }
        process.stdin.pause();
      }
      process.stdin.removeListener('data', onData);
      process.removeListener('SIGINT', onSigint);
      process.stdout.write('\n');
    };

    if (useRaw) {
      try { process.stdin.setRawMode(true); } catch { /* noop */ }
      process.stdin.resume();
      process.stdin.on('data', onData);
    }
    process.on('SIGINT', onSigint);

    render();
    const timer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        cleanup();
        resolve(ctrl);
        return;
      }
      render();
    }, 1000);
  });
}

async function runPomodoroSession(config: PomodoroConfig, focusQuery?: string, breakQuery?: string) {
  const totalFocuses = config.cyclesBeforeLongBreak;
  const plan = buildSessionPlan(config);
  console.log('');
  printCard('POMODORO SESSION', [
    `Focus  ${config.focusMinutes} min × ${totalFocuses}`,
    `Break  ${config.shortBreakMinutes} min · Long ${config.longBreakMinutes} min`,
    ui.dim('s skip phase · Esc stop music · q quit'),
  ]);
  console.log('');

  let focusSearchCache: VideoInfo[] | null = null;
  if (focusQuery) {
    printStatus('info', `Finding focus music: "${focusQuery}"`);
    focusSearchCache = await searchYouTube(focusQuery);
    if (focusSearchCache.length === 0) printStatus('warning', 'No focus music found · timer will run silent');
    else printStatus('success', `Focus track ready: ${focusSearchCache[0]?.title ?? 'unknown'}`);
  }

  let completedFocuses = 0;
  const startedAt = Date.now();

  for (const item of plan) {
    const isFocus = item.phase === 'focus';
    const musicQuery = isFocus ? focusQuery : breakQuery;
    const cache = isFocus ? focusSearchCache : null;
    const icon = isFocus ? 'FOCUS' : 'BREAK';
    console.log('');
    printCard(`${icon} · ${item.label.toUpperCase()}`, [
      `${formatCountdown(item.durationSeconds)} remaining`,
      ui.dim(isFocus ? 'Lock in. Your music starts below.' : 'Step away. Breathe. Reset.'),
    ]);
    console.log('');

    // Start music for this phase (best-effort, shell-free).
    let ffplay: ReturnType<typeof spawn> | null = null;
    try {
      let track: VideoInfo | undefined;
      if (musicQuery && isFocus && cache && cache.length > 0) {
        track = cache[Math.min(completedFocuses, cache.length - 1)];
      } else if (musicQuery && !isFocus) {
        const res = await searchYouTube(musicQuery);
        track = res[0];
      }
      if (track) {
        const streamUrl = await resolveAudioUrlNoShell(track.url);
        ffplay = spawn('ffplay', ['-nodisp', '-autoexit', '-loglevel', 'quiet', streamUrl], {
          stdio: 'ignore',
        });
        ffplay.on('error', () => { ffplay = null; });
        printStatus('success', `Playing: ${track.title}`);
      }
    } catch (e) {
      printStatus('warning', `Music skipped: ${e instanceof Error ? e.message : e}`);
    }

    const stopMusic = () => {
      if (ffplay && !ffplay.killed) {
        ffplay.kill();
        ffplay = null;
      }
    };
    const ctrl = await countdownWithKeys(item.durationSeconds, `${icon} ${item.label}`, stopMusic);
    stopMusic();

    if (ctrl.quit) {
      printStatus('warning', 'Pomodoro quit');
      break;
    }
    if (isFocus && !ctrl.skipped) completedFocuses += 1;
    process.stdout.write('\x07'); // bell
    printStatus(ctrl.skipped ? 'warning' : 'success', ctrl.skipped ? 'Phase skipped' : isFocus ? 'Focus done · take a break' : 'Break over · back to focus');
    if (ctrl.skipped && isFocus) completedFocuses += 0;
  }

  const mins = Math.round((Date.now() - startedAt) / 60000);
  console.log('');
  printCard('SESSION COMPLETE', [
    `${completedFocuses}/${totalFocuses} focus blocks completed`,
    `~${mins} minutes elapsed`,
  ]);
  console.log('');
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help') || argv.includes('-h')) {
    printHelp();
    process.exit(0);
  }
  if (argv.includes('--version') || argv.includes('-V')) {
    try {
      const pkg = await Bun.file('package.json').json() as { version?: string };
      console.log(`music-cli v${pkg.version ?? '0.0.0'}`);
    } catch {
      console.log('music-cli v0.0.0');
    }
    process.exit(0);
  }

  const pomo = parsePomodoroCliArgs(argv);
  if (pomo.enabled) {
    if (pomo.error) {
      console.error(`❌ ${pomo.error}`);
      process.exit(2);
    }
    // Positional query fallback: `music --pomodoro lofi` (any non-flag args).
    const positional = argv.filter((a) => !a.startsWith('--') && a !== pomo.query && a !== pomo.breakQuery);
    // Remove argv values already consumed (best-effort): if --query not given, use positionals.
    const focusQuery = pomo.query ?? (positional.length > 0 ? positional.join(' ') : undefined);
    await runPomodoroSession(pomo.config, focusQuery || undefined, pomo.breakQuery || undefined);
    process.exit(0);
  }

  // Positional query shortcut: `music lofi hip hop` → skip first prompt once.
  let initialQuery: string | undefined;
  const positionalQuery = argv.filter((a) => !a.startsWith('-')).join(' ').trim();
  if (positionalQuery) initialQuery = positionalQuery;

  printBanner();

  while (true) {
    try {
      // Get search query from user (or use positional `music lofi hip hop` once)
      let query: string;
      if (initialQuery) {
        query = initialQuery;
        initialQuery = undefined;
        printStatus('info', `Search: "${query}"`);
      } else {
        query = await input({
          message: 'Search for music (ESC to exit):',
        });
      }

      if (!query.trim()) {
        console.log('Please enter a search query\n');
        continue;
      }

      console.log('');

      // Search YouTube
      const results = await searchYouTube(query);

      if (results.length === 0) {
        printStatus('warning', `No results for "${query}" · try artist + song`);
        console.log('');
        continue;
      }

      // Keep showing the same results until user finishes a song naturally
      let continueWithSameResults = true;
      while (continueWithSameResults) {
        // Let user select a video
        const choices = [
          {
            name: '←  Search again',
            value: null, // Special value to indicate new search
          },
          ...results.map((video) => ({
            name: `${ui.cyan('›')} ${video.title} ${ui.dim(`— ${video.author.name} · ${video.duration.timestamp}`)}`,
            value: video,
          })),
        ];

        const selectedVideo = await select({
          message: 'Select a track (or choose "Search again"):',
          choices,
        });

        // If user chose to search again
        if (selectedVideo === null) {
          console.log('');
          printStatus('info', 'New search');
          console.log('');
          break; // Exit the inner loop to get new search query
        }

        console.log('');
        printCard('NOW PLAYING', [
          ui.cyan(selectedVideo.title),
          `${selectedVideo.author.name} · ${selectedVideo.duration.timestamp}`,
        ]);
        console.log('');

        // Play the selected video
        const { stoppedByUser } = await playAudio(selectedVideo.url, selectedVideo.duration.timestamp);

        // If stopped by user (Esc), show the same results again
        // If finished naturally, exit loop and ask for new search
        continueWithSameResults = stoppedByUser;
      }

    } catch (error) {
      if (error instanceof Error && error.message.includes('User force closed')) {
        console.log('\n👋 Goodbye!\n');
        process.exit(0);
      }
      console.error('Error:', error);
      console.log('\n');
    }
  }
}

main();
