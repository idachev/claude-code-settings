---
name: msg-notify
description: Use when work is blocked on Ivan's decision, approval, or answer and he may not be watching the chat, or when asked to ping his phone, send a push, or use msg-notifier or notify.sh.
---

# msg-notify

Ping Ivan's phone through msg-notifier, but only when he is away from the laptop.
The global rule "Notify Ivan Only When He Is Away From The Laptop" in
`~/.claude/CLAUDE.md` decides when; this skill is the how.

## Send

```bash
GATE="$HOME/.claude/scripts/notify-when-away.sh"
NOTIFY="$HOME/develop/personal/msg-notifier/utils/scripts/notify.sh"
"$GATE" "$NOTIFY" claude "short question"
"$GATE" "$NOTIFY" claude -t "Short title" -m "More context"
```

- Always send through `$GATE`. It returns at once and runs `notify.sh` only after
  15 minutes with no keyboard, mouse or trackpad input; any input drops the ping.
  Log: `~/.claude/logs/notify-when-away.log`.
- Always put the same question in the chat. The ping is only a copy.
- One decision per ping. No routine progress pings.
- Source is who you are: Claude → `claude`, Grok / xAI → `grok`.
- Run `"$NOTIFY" --help` for flags.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Calling `"$NOTIFY"` directly | Prefix it with `"$GATE"`, every time |
| Question only in the ping | Write it in the chat too |
| Several questions in one ping | One ping per decision |

`notify.sh` sends through Mail.app via `osascript`, so it works only on macOS.
Elsewhere it fails; ask in the chat instead.
