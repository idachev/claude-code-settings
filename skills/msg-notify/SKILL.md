---
name: msg-notify
description: Use when Ivan may not be watching the chat and you need a decision, approval, or unblock — ping laptop, Pushover, msg-notifier, notify.sh.
---

# msg-notify

Ping Ivan on the laptop via msg-notifier. Do not wait silently if a choice is blocking work.

## When

Ping if all are true:

- You need a decision, approval, or an answer to continue
- The question is waiting on Ivan, not on more code
- He may be away from this chat (laptop, another app)

Do not ping for routine progress. Do not ping if he is already answering in this chat.

## Command

```bash
NOTIFY=/Users/idachev/develop/personal/msg-notifier/utils/scripts/notify.sh
"$NOTIFY" grok "short question"
"$NOTIFY" claude -t "Short title" -m "More context"
```

Pick the source from who you are:

- Grok / xAI → `grok`
- Claude → `claude`

Keep one decision per ping. Run `--help` for flags. Mail.app sends to `msg-notifier@codewithaivan.com`. Ivan acks in Pushover.
