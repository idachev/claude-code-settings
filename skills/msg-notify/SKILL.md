---
name: msg-notify
description: Use when Ivan may not be watching the chat and you need a decision, approval, or unblock — ping laptop, msg-notifier, notify.sh.
---

# msg-notify

Ping Ivan on the laptop via msg-notifier. Do not wait silently if a choice is blocking work.

## When

Ping if all are true:

- You need a decision, approval, or an answer to continue
- The question is waiting on Ivan, not on more code
- He has not paid attention to this chat for more than 5 minutes

Do not ping for routine progress. Do not ping if he is in this chat. A message from him, even a short one, means he is here. Wait at least 5 minutes of no attention before a ping.

## Command

```bash
NOTIFY="$HOME/develop/personal/msg-notifier/utils/scripts/notify.sh"
"$NOTIFY" grok "short question"
"$NOTIFY" claude -t "Short title" -m "More context"
```

Pick the source from who you are:

- Grok / xAI → `grok`
- Claude → `claude`

Keep one decision per ping. Run `--help` for flags.

`notify.sh` sends through Mail.app via `osascript`, so it works only on macOS. On linux the script fails; say the question in the chat instead.
