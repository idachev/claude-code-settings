---
name: msg-notify
description: Use when Ivan may not be watching the chat and you need a decision, approval, or unblock — ping laptop, msg-notifier, notify.sh.
---

# msg-notify

Ping Ivan's phone via msg-notifier. Do not wait silently if a choice is blocking work.

## When

The global rule "Notify Ivan Only When He Is Away From The Laptop" in `~/.claude/CLAUDE.md`
decides when a ping may go out. Ping only if all are true:

- You need a decision, approval, or an answer to continue
- The question is waiting on Ivan, not on more code
- The ping goes through the away gate below; the gate drops it if he touches the laptop
  within 15 minutes of the event

Do not ping for routine progress. Never call `notify.sh` without the gate. Put the
question in the chat as well; the ping is only a copy for when he is away.

## Command

```bash
GATE="$HOME/.claude/scripts/notify-when-away.sh"
NOTIFY="$HOME/develop/personal/msg-notifier/utils/scripts/notify.sh"
"$GATE" "$NOTIFY" grok "short question"
"$GATE" "$NOTIFY" claude -t "Short title" -m "More context"
```

The gate returns at once and waits in the background. Its log is
`~/.claude/logs/notify-when-away.log`.

Pick the source from who you are:

- Grok / xAI → `grok`
- Claude → `claude`

Keep one decision per ping. Run `"$NOTIFY" --help` for flags.

`notify.sh` sends through Mail.app via `osascript`, so it works only on macOS. On linux the script fails; say the question in the chat instead.
