#!/bin/sh
# Run a notification command only when Ivan is away from this laptop.
#
# Usage: notify-when-away.sh <command> [args...]
#
# Returns at once. A detached waiter watches keyboard, mouse and trackpad input
# (macOS HIDIdleTime) for AWAY_SECONDS after the event. Any input in that window
# means Ivan is at the laptop and sees the chat, so the command is dropped.
# No input for the whole window means he is away, so the command runs.
# The command and its arguments are run as given; they are never evaluated.
#
# Env overrides (for tests): AWAY_SECONDS (default 900; 0 runs at once; a bad
# value gives the default), AWAY_POLL (default 20),
# AWAY_LOG (default ~/.claude/logs/notify-when-away.log), AWAY_FAKE_IDLE (fixed
# idle seconds instead of the real reading).

start=$(date +%s)   # the event time; taken first, before any other work

# A whole number of seconds: digits only, at most four, leading zeros stripped
# (08 is not octal). Anything else gives the default, so the arithmetic below
# can never fail. Usage: seconds <value> <default> <minimum>
seconds() {
    case $1 in
        '' | *[!0-9]* | ?????*) echo "$2"; return ;;
    esac
    value=${1#"${1%%[!0]*}"}
    value=${value:-0}
    if [ "$value" -lt "$3" ]; then echo "$2"; else echo "$value"; fi
}

window=$(seconds "${AWAY_SECONDS:-}" 900 0)
poll=$(seconds "${AWAY_POLL:-}" 20 1)
AWAY_LOG=${AWAY_LOG:-$HOME/.claude/logs/notify-when-away.log}

if [ "$#" -lt 1 ]; then
    echo 'usage: notify-when-away.sh <command> [args...]' >&2
    exit 2
fi

# Seconds since the last HID input; empty when it cannot be read (not macOS).
idle_seconds() {
    [ -n "${AWAY_FAKE_IDLE:-}" ] && { echo "$AWAY_FAKE_IDLE"; return; }
    ioreg -c IOHIDSystem 2>/dev/null | awk '/HIDIdleTime/ {print int($NF / 1000000000); exit}'
}

log() {
    printf '%s pid=%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$$" "$*"
}

# Succeeds when no input arrives during the whole window after the event, or
# when idle time cannot be read (then it sends, as before the gate existed).
# Fails on input inside the window. The clock has whole seconds, so input up to
# one second before the event counts as inside. The last sleep is cut to the
# time left, and input after the window end does not count.
stays_away() {
    while :; do
        elapsed=$(( $(date +%s) - start ))
        left=$(( window - elapsed ))
        [ "$left" -le 0 ] && return 0
        [ "$left" -lt "$poll" ] && poll=$left
        sleep "$poll"
        idle=$(idle_seconds)
        case $idle in
            '' | *[!0-9]*) log "idle time unknown, sending"; return 0 ;;
        esac
        elapsed=$(( $(date +%s) - start ))
        input_at=$(( elapsed - idle ))   # seconds after the event, may be negative
        if [ "$input_at" -ge -1 ] && [ "$input_at" -lt "$window" ]; then
            log "input ${input_at}s after the event: at the laptop, dropped"
            return 1
        fi
    done
}

wait_then_run() {
    log "queued for ${window}s: $*"
    stays_away || return 0
    log "no input for ${window}s: away, sending"
    "$@"
    log "exit=$?"
}

mkdir -p "$(dirname "$AWAY_LOG")"
# Detach so the caller (a Bash tool call) is not held for 15 minutes.
( trap '' HUP; wait_then_run "$@" ) </dev/null >>"$AWAY_LOG" 2>&1 &
echo "notify-when-away: queued, sends in ${window}s only if there is no input (log: $AWAY_LOG)" >&2
exit 0
