#!/usr/bin/env bash
# transcribe-srt-pool.sh — spawn N parallel transcribe-srt-worker.sh workers.
#
# Usage:
#   transcribe-srt-pool.sh --workers N --glob "<glob>" [--model MODEL] [--log-dir DIR] [-- EXTRACT_SRT_ARGS...]
#
# Spawns N independent worker processes, each running its own scan/claim/run loop
# with mkdir-atomic locks under the MP4 dir. The dedup invariant is enforced by
# `mkdir <base>.transcribing.lock` (POSIX-atomic) - workers never collide.
#
# Writes the PID list to <log-dir>/transcribe-srt-pool.pids so transcribe-srt-status.sh
# can introspect the pool. Returns immediately - workers run detached.
#
# Notes:
# - --glob is passed verbatim to each worker; quote it to defer expansion to the worker.
# - Workers exit when there's no available work for `--max-idle` consecutive scans.

set -u

SCRIPT_DIR="$(command cd -- "$(command dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SCRIPT="${SCRIPT_DIR}/transcribe-srt-worker.sh"
DEFAULT_LOG_DIR="${TMPDIR:-/tmp}/transcribe-srt-logs"

WORKERS=""
GLOB=""
MODEL=""   # empty = the default model of extract-srt.py
LOG_DIR="$DEFAULT_LOG_DIR"
MAX_IDLE=3
EXTRA_ARGS=()

usage() {
  command sed -n '2,18p' "$0" | command sed 's/^# \?//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --workers)  WORKERS="$2"; shift 2 ;;
    --glob)     GLOB="$2"; shift 2 ;;
    --model)    MODEL="$2"; shift 2 ;;
    --log-dir)  LOG_DIR="$2"; shift 2 ;;
    --max-idle) MAX_IDLE="$2"; shift 2 ;;
    -h|--help)  usage 0 ;;
    --)         shift; EXTRA_ARGS=("$@"); break ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done

[ -n "$WORKERS" ] || { echo "ERROR: --workers N is required" >&2; exit 2; }
[ -n "$GLOB" ]    || { echo "ERROR: --glob is required" >&2; exit 2; }
[ -x "$WORKER_SCRIPT" ] || { echo "ERROR: worker script not executable: $WORKER_SCRIPT" >&2; exit 2; }

command mkdir -p "$LOG_DIR"
PID_FILE="${LOG_DIR}/transcribe-srt-pool.pids"

# Preserve PIDs of any still-running workers (the pool grows by re-running this
# script). Only truncate when every prior PID has exited, so
# stale dead PIDs don't accumulate across unrelated batches.
any_alive=0
if [ -f "$PID_FILE" ]; then
  while IFS=$'\t' read -r prev_pid _ _; do
    [ -n "${prev_pid:-}" ] || continue
    if command kill -0 "$prev_pid" 2>/dev/null; then any_alive=1; break; fi
  done < "$PID_FILE"
fi
if [ "$any_alive" -eq 0 ]; then
  : > "$PID_FILE"
else
  echo "appending to existing pool ($PID_FILE)"
fi

MODEL_ARGS=()
[ -z "$MODEL" ] || MODEL_ARGS=(--model "$MODEL")

echo "spawning $WORKERS workers (model=${MODEL:-default}  log-dir=$LOG_DIR)"
echo "glob: $GLOB"
echo "PID file: $PID_FILE"

STAMP="$(command date +%Y%m%d-%H%M%S)"
for i in $(command seq 1 "$WORKERS"); do
  worker_log="${LOG_DIR}/transcribe-srt-pool-w${i}-${STAMP}.log"
  nohup "$WORKER_SCRIPT" \
    --id "$i" \
    --glob "$GLOB" \
    ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"} \
    --log-dir "$LOG_DIR" \
    --max-idle "$MAX_IDLE" \
    ${EXTRA_ARGS[@]+-- "${EXTRA_ARGS[@]}"} \
    > "$worker_log" 2>&1 &
  pid=$!
  command printf '%s\tw%s\t%s\n' "$pid" "$i" "$worker_log" >> "$PID_FILE"
  echo "  worker $i: PID $pid  log=$worker_log"
  command disown 2>/dev/null
done

echo ""
echo "all $WORKERS workers detached. Check status:"
echo "  ${SCRIPT_DIR}/transcribe-srt-status.sh --log-dir $LOG_DIR --glob \"$GLOB\""
