---
name: transcribe-srt
description: Use when turning a video or a recording into subtitles or a transcript, producing or re-producing an .srt for one MP4 or a whole folder of MP4s, resuming a failed transcription, or checking transcription progress. Triggers include "transcribe this video", "generate SRT", "extract subtitles", "субтитри", "транскрибирай", "transcribe pool", "transcribe progress".
---

# Transcribe to SRT

Whisper gives the timestamps. Gemini listens to the same audio and gives the text.
The result is an SRT with accurate timing and accurate words. Scripts live in
`scripts/` next to this file; `<skill-dir>` below is this skill's base directory.

| Case | Use |
|---|---|
| One video | `scripts/extract-srt.py` |
| Many videos | `scripts/transcribe-srt-pool.sh`, then `scripts/transcribe-srt-status.sh` |

## Prerequisites

Check these first, without printing secrets:

```bash
python3 -c "import os; print('OPENAI', 'yes' if os.environ.get('OPENAI_API_KEY') else 'no'); print('GEMINI_KEY', 'yes' if os.environ.get('GEMINI_API_KEY') else 'no')"
```

- `OPENAI_API_KEY` must be in this process. The script does not read `.env`.
- macOS or Linux, with `ffmpeg`, `ffprobe`, `curl`, `python3` 3.10+. The pool also needs bash 4+.
- One Gemini login:

| `--gemini-auth` | Needs | Notes |
|---|---|---|
| `auto` (default) | either login below | Vertex when usable, otherwise the API key |
| `vertex` | `gcloud auth login` (or `GEMINI_VERTEX_TOKEN`), and `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT` or a gcloud default project | Flex tier by default (half price, slower). `GEMINI_SERVICE_TIER=standard` for the fast tier |
| `api-key` | `GEMINI_API_KEY` | Gemini Developer API. `GEMINI_SERVICE_TIER` does not apply |

A session inherits the environment of the shell that started it. If a key is missing,
ask the user to export it there and restart the session.

## One video

```bash
LOG="extract-srt-$(date +%Y%m%d-%H%M%S).log"
python3 -u <skill-dir>/scripts/extract-srt.py --workers 6 "<path/to/video.mp4>" > "$LOG" 2>&1
echo "EXIT=$?"; tail -n 40 "$LOG"
```

| Flag | Default | Purpose |
|---|---|---|
| `--language CODE` | `bg` | Spoken language, ISO 639-1. `--help` lists the codes |
| `--gemini-model NAME` | the `GEMINI_MODEL` constant in the script | Model for transcribe and realign |
| `--gemini-auth MODE` | `auto` | See the table above |
| `--workers N` | `1` | Parallel Gemini work per video. Use 4 to 8 over an hour of audio |

Audio is cut into chunks of at most 10 minutes without overlap, so a word on a chunk
boundary can be lost. Run long videos in the background.

Written next to the video: `<base>.srt` (final), `<base>-raw.srt` (Whisper only).
A trailing `-compressed` in the name is removed. Add `.extract-srt-cache/` to `.gitignore`.

## Resume

Re-run the same command. Every finished stage in `<video-dir>/.extract-srt-cache/` is
reused. Changing the model or the language redoes only the affected stages. Delete that
directory for a cold run.

## Many videos

```bash
<skill-dir>/scripts/transcribe-srt-pool.sh --workers 4 --glob "**/*.mp4" \
  --log-dir ./tmp/transcribe-logs -- --language bg
<skill-dir>/scripts/transcribe-srt-status.sh --glob "**/*.mp4" --log-dir ./tmp/transcribe-logs
```

- Run from the corpus root. Quote the glob. Keep `--log-dir` gitignored.
- Keep one video per directory. Cache and lock are per directory, so two videos in one
  directory cannot run together: the second worker logs `FAIL` and retries later.
- Videos under 1 MiB are skipped as unfinished downloads. Run `extract-srt.py` on them directly.
- Arguments after `--` go to `extract-srt.py` unchanged. `--model` sets the model.
- Each video is claimed with `mkdir <base>.transcribing.lock`, so workers never collide.
  A video that already has `<base>.srt` is skipped.
- More workers: run the pool again. Live view: add `--watch 60` to status.
- Stop after the current video:

```bash
awk '{print $1}' ./tmp/transcribe-logs/transcribe-srt-pool.pids | xargs kill -TERM
```

- After a hard kill: `find . -name '*.transcribing.lock' -type d -empty -delete`.

## Common failures

| Symptom | Fix |
|---|---|
| `Another extract-srt.py is already running` | Never run two on one video. If none runs, delete `.extract-srt-cache/.lock` |
| `Realign failed for chunk N/M` or `truncated the transcript` | No final SRT on purpose, so a partial result never passes as done. Re-run the same command; finished chunks are cached |
| Final SRT has far fewer segments | Gemini collapsed segments. Use a Pro model, not Flash |
| `realign` returns empty with `finishReason=STOP` | The model cannot realign. `gemini-3.5-transcribe` does this; use a general model |
| `Flex API is not supported` | The model has no Flex tier on Vertex. Set `GEMINI_SERVICE_TIER=standard` |
| HTTP 403 with `auto` although a key is set | Vertex was usable but not allowed. Pass `--gemini-auth api-key` |
| HTTP 429 or `RESOURCE_EXHAUSTED` | Lower the workers. Above 12 pool workers Whisper throttles |
| Pool workers exit at once | The glob matches nothing, or every video has an SRT |

## Tests

`python3 -m unittest discover -s tests` from the skill directory. Offline, no keys.
