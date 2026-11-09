#!/usr/bin/env bash
# transcribe-srt-status.sh — show progress of a transcribe-srt-pool run.
#
# Usage:
#   transcribe-srt-status.sh --glob "<glob>" [--log-dir DIR] [--watch SECONDS]
#
# Reports:
#   - Per-group SRT progress (groups = the parent-of-parent directory of each MP4)
#   - Currently-locked MP4s (= active workers)
#   - Live worker PIDs from <log-dir>/transcribe-srt-pool.pids
#   - Recent throughput (SRTs created in last N minutes)
#   - Any FAIL or rate-limit entries in worker logs

set -u
[ "${BASH_VERSINFO[0]}" -ge 4 ] || { echo "ERROR: needs bash 4 or newer (globstar, associative arrays)" >&2; exit 2; }
# globstar so a caller-supplied "**/*.mp4" recurses; nullglob so an empty match
# yields no iterations instead of looping on the literal pattern.
shopt -s globstar nullglob

DEFAULT_LOG_DIR="${TMPDIR:-/tmp}/transcribe-srt-logs"
GLOB=""
LOG_DIR="$DEFAULT_LOG_DIR"
WATCH=""
RATE_WINDOW=10   # minutes

usage() {
  command sed -n '2,16p' "$0" | command sed 's/^# \?//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --glob)        GLOB="$2"; shift 2 ;;
    --log-dir)     LOG_DIR="$2"; shift 2 ;;
    --watch)       WATCH="$2"; shift 2 ;;
    --rate-window) RATE_WINDOW="$2"; shift 2 ;;
    -h|--help)     usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done

[ -n "$GLOB" ] || { echo "ERROR: --glob is required" >&2; exit 2; }

render() {
  command printf '=== transcribe-srt-status @ %s ===\n' "$(command date '+%Y-%m-%d %H:%M:%S')"

  # Per-group SRT/MP4 table - derived from the glob.
  # We expand the glob and group by the *parent of parent* dir
  # (e.g. <root>/<group>/<item>/<item>.mp4 -> tally under <group>).
  echo ""
  echo "Progress per group:"
  command printf '  %-55s %12s %10s\n' "group" "srt/mp4" "%"
  command printf '  %-55s %12s %10s\n' "------------------------------------------------------" "------------" "----------"

  declare -A G_MP4 G_SRT
  TOT_MP4=0; TOT_SRT=0
  # shellcheck disable=SC2086
  for mp4 in $GLOB; do
    [ -f "$mp4" ] || continue
    group_dir=$(command dirname "$(command dirname "$mp4")")
    group_name=$(command basename "$group_dir")
    base="${mp4%.mp4}"
    G_MP4[$group_name]=$((${G_MP4[$group_name]:-0} + 1))
    TOT_MP4=$((TOT_MP4 + 1))
    if [ -f "${base%-compressed}.srt" ]; then
      G_SRT[$group_name]=$((${G_SRT[$group_name]:-0} + 1))
      TOT_SRT=$((TOT_SRT + 1))
    fi
  done
  # Read line by line: a group name may contain spaces.
  while IFS= read -r g; do
    [ -n "$g" ] || continue
    m=${G_MP4[$g]}; s=${G_SRT[$g]:-0}
    pct=$(command awk "BEGIN { printf \"%5.1f%%\", ($s/$m)*100 }")
    command printf '  %-55s %12s %10s\n' "$g" "${s}/${m}" "$pct"
  done < <(command printf '%s\n' "${!G_MP4[@]}" | command sort)
  command printf '  %-55s %12s %10s\n' "------------------------------------------------------" "------------" "----------"
  if [ "$TOT_MP4" -gt 0 ]; then
    pct=$(command awk "BEGIN { printf \"%5.1f%%\", ($TOT_SRT/$TOT_MP4)*100 }")
  else
    pct="  -   "
  fi
  command printf '  %-55s %12s %10s\n' "TOTAL" "${TOT_SRT}/${TOT_MP4}" "$pct"

  # Current locks (= active transcribes).
  echo ""
  echo "Currently transcribing (lock = active worker):"
  found=0
  # shellcheck disable=SC2086
  for mp4 in $GLOB; do
    base="${mp4%.mp4}"
    lock="${base}.transcribing.lock"
    [ -d "$lock" ] || continue
    found=1
    # GNU stat first, BSD stat (macOS) as the fallback.
    age_sec=$(command stat -c %Y "$lock" 2>/dev/null || command stat -f %m "$lock" 2>/dev/null)
    # Lock may have vanished between the -d test and stat; default to "now" so
    # the arithmetic stays well-formed instead of producing a syntax error.
    age_min=$(( ( $(command date +%s) - ${age_sec:-$(command date +%s)} ) / 60 ))
    rel=$(command basename "$(command dirname "$base")")/$(command basename "$base")
    command printf '  %-50s  started %sm ago\n' "$rel" "$age_min"
  done
  [ $found -eq 0 ] && echo "  (no active workers)"

  # Worker pool PIDs.
  PID_FILE="${LOG_DIR}/transcribe-srt-pool.pids"
  if [ -f "$PID_FILE" ]; then
    echo ""
    echo "Worker pool (from $PID_FILE):"
    alive=0; total=0
    while IFS=$'\t' read -r pid wid log; do
      total=$((total + 1))
      if command kill -0 "$pid" 2>/dev/null; then
        alive=$((alive + 1))
        etime=$(command ps -o etime= -p "$pid" 2>/dev/null | command tr -d ' ')
        command printf '  %-6s PID %-8s alive %s\n' "$wid" "$pid" "$etime"
      else
        command printf '  %-6s PID %-8s DEAD\n' "$wid" "$pid"
      fi
    done < "$PID_FILE"
    echo "  -> $alive/$total workers alive"
  fi

  # Throughput in last N minutes. Search dirs derived from the glob's matching MP4s.
  echo ""
  recent=0
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    dir_recent=$(command find "$dir" -maxdepth 1 -name '*.srt' ! -name '*-raw.srt' -mmin -"$RATE_WINDOW" 2>/dev/null | command wc -l)
    recent=$((recent + dir_recent))
  done < <(for mp4 in $GLOB; do command dirname "$mp4"; done | command sort -u)
  rate_per_hour=$(command awk "BEGIN { printf \"%.0f\", $recent * (60.0 / $RATE_WINDOW) }")
  echo "Throughput: $recent SRTs in last ${RATE_WINDOW}m  (~${rate_per_hour}/hour)"

  # Errors in worker logs since last hour.
  # The worker writes FAIL to its pool log; extract-srt.py errors go to the per-video log.
  fail_logs=$(command find "$LOG_DIR" \( -name '*-transcribe-w*.log' -o -name 'transcribe-srt-pool-w*.log' \) -mmin -60 \
    -exec grep -l -E "FAIL|RESOURCE_EXHAUSTED|rate.limit|429" {} + 2>/dev/null)
  if [ -n "$fail_logs" ]; then
    echo ""
    echo "WARN: failures/rate-limits in worker logs (last hour):"
    echo "$fail_logs" | command head -n 5
  fi
}

if [ -n "$WATCH" ]; then
  while true; do
    command clear
    render
    sleep "$WATCH"
  done
else
  render
fi
