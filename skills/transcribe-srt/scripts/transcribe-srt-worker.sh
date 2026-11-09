#!/usr/bin/env bash
# transcribe-srt-worker.sh — single parallel-pool worker that drives extract-srt.py.
#
# Usage:
#   transcribe-srt-worker.sh --id N --glob "<glob>" [--model MODEL] [--max-idle N] [-- EXTRACT_SRT_ARGS...]
#
# Behaviour: loops forever finding MP4s under --glob that lack a `.srt` sibling
# and aren't currently locked. Claims one with an atomic `mkdir <base>.transcribing.lock`,
# invokes extract-srt.py, releases the lock. Exits when N consecutive idle scans
# find nothing to do.
#
# The dedup invariant: `mkdir` is a POSIX-atomic operation. Two workers racing
# the same MP4 - exactly one mkdir succeeds, the other gets EEXIST and skips.
#
# Output: per-worker log on stdout; per-MP4 extract-srt.py log written to
# <log-dir>/<mp4-basename>-transcribe-w<id>.log.

set -u
[ "${BASH_VERSINFO[0]}" -ge 4 ] || { echo "ERROR: needs bash 4 or newer (globstar)" >&2; exit 2; }
# globstar so callers can pass "**/*.mp4" and have it recurse; nullglob so an
# unmatched glob yields an empty loop instead of iterating on the literal pattern.
shopt -s globstar nullglob

SCRIPT_DIR="$(command cd -- "$(command dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRACT_SRT="${SCRIPT_DIR}/extract-srt.py"
WORKER_ID=""
GLOB=""
MODEL=""   # empty = the default model of extract-srt.py
EXTRA_ARGS=()
LOG_DIR="${TMPDIR:-/tmp}/transcribe-srt-logs"
MAX_IDLE_SCANS=3
SCAN_SLEEP=20
SIZE_STABILITY_SLEEP=3

usage() {
  command sed -n '2,18p' "$0" | command sed 's/^# \?//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --id)        WORKER_ID="$2"; shift 2 ;;
    --glob)      GLOB="$2"; shift 2 ;;
    --model)     MODEL="$2"; shift 2 ;;
    --log-dir)   LOG_DIR="$2"; shift 2 ;;
    --max-idle)  MAX_IDLE_SCANS="$2"; shift 2 ;;
    -h|--help)   usage 0 ;;
    --)          shift; EXTRA_ARGS=("$@"); break ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done
[ -z "$MODEL" ] || EXTRA_ARGS=(--gemini-model "$MODEL" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"})

[ -n "$WORKER_ID" ] || { echo "ERROR: --id is required" >&2; exit 2; }
[ -n "$GLOB" ]      || { echo "ERROR: --glob is required" >&2; exit 2; }
[ -x "$EXTRACT_SRT" ] || [ -f "$EXTRACT_SRT" ] || { echo "ERROR: extract-srt.py not found next to this script ($EXTRACT_SRT)" >&2; exit 2; }
command mkdir -p "$LOG_DIR"

log() { command printf '%s [w%s] %s\n' "$(command date '+%H:%M:%S')" "$WORKER_ID" "$*"; }
# Portable size: GNU and BSD stat take different flags. 0 when the file is gone.
file_size() { local n; n=$(command wc -c 2>/dev/null < "$1"); echo "$(( ${n:-0} ))"; }

# bash runs a trap only after the foreground command ends, so TERM lets the
# current video finish and release its lock.
STOP_REQUESTED=0
trap 'STOP_REQUESTED=1' TERM
exit_if_stop_requested() {
  [ "$STOP_REQUESTED" -eq 1 ] || return 0
  log "EXIT - stop requested"
  exit 0
}

log "START worker (model=${MODEL:-default}  glob=$GLOB  log-dir=$LOG_DIR)"

idle_count=0
while true; do
  worked=0
  # Use the glob expansion in the parent shell (caller controls what's matched).
  # shellcheck disable=SC2086
  for mp4 in $GLOB; do
    exit_if_stop_requested
    [ -f "$mp4" ] || continue
    base="${mp4%.mp4}"
    # extract-srt.py drops a trailing -compressed from the output name.
    srt="${base%-compressed}.srt"
    [ -f "$srt" ] && continue
    lock="${base}.transcribing.lock"
    [ -e "$lock" ] && continue

    # Atomic claim first so only one worker pays the stability cost.
    # If mkdir fails, another worker won the race - skip immediately.
    if ! command mkdir "$lock" 2>/dev/null; then continue; fi

    # Stability gate: if size is changing (still downloading) or file is too small
    # to be a real video, release the lock and try again on a later scan.
    sz1=$(file_size "$mp4")
    sleep "$SIZE_STABILITY_SLEEP"
    sz2=$(file_size "$mp4")
    if [ "$sz1" != "$sz2" ] || [ "$sz2" -lt 1048576 ]; then
      log "skip $mp4 (unstable or <1MB: sz1=$sz1 sz2=$sz2)"
      command rmdir "$lock" 2>/dev/null
      continue
    fi

    slog="${LOG_DIR}/$(command basename "$base")-transcribe-w${WORKER_ID}.log"
    log "START $mp4 (size $sz2)  log=$slog"
    "$EXTRACT_SRT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$mp4" > "$slog" 2>&1
    rc=$?
    command rmdir "$lock" 2>/dev/null

    if [ $rc -eq 0 ] && [ -f "$srt" ]; then
      log "DONE  $srt ($(file_size "$srt") bytes)"
      worked=1
    else
      log "FAIL  $mp4 rc=$rc  --- tail of $slog ---"
      command tail -n 6 "$slog" 2>&1
    fi
  done

  exit_if_stop_requested
  if [ $worked -eq 1 ]; then
    idle_count=0
  else
    idle_count=$((idle_count + 1))
    log "idle scan $idle_count/$MAX_IDLE_SCANS - no available work"
    if [ "$idle_count" -ge "$MAX_IDLE_SCANS" ]; then
      log "EXIT - no work after $MAX_IDLE_SCANS scans"
      exit 0
    fi
    sleep "$SCAN_SLEEP"
  fi
done
