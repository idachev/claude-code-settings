---
name: new-android-app
description: Use when Ivan asks to start a new personal Android app, to scaffold an Android project, or to set up build and APK deploy conventions for one. Starts from the latest official Android CLI template and copies the conventions of ~/develop/personal/financy and meet-no-miss.
---

# New personal Android app

Start every new personal Android app from the official Google template, not from
a hand-written Gradle setup. The template's version set is known to compile, and
shared conventions keep Ivan's apps consistent.

## 1. Update the CLI and create the project

The Android CLI is `~/.local/bin/android`. Update it first so the template is
the latest one. If the update fails, show the error and ask before going on with
the installed version.

Pick three names before running `create`:

- `<Label>` — the visible app name, e.g. `Meet No Miss`;
- `<repo-name>` — kebab-case folder under `~/develop/personal/`, also used for
  the Dropbox folder and the APK name, e.g. `meet-no-miss`;
- `<segment>` — lowercase letters and digits only, starting with a letter, not a
  Java/Kotlin keyword; the package is `com.idachev.<segment>`, e.g. `meetnomiss`.

If the label has more than one word, ask Ivan for `<repo-name>` and `<segment>`.

```bash
command ~/.local/bin/android update
command ~/.local/bin/android create \
  --name="<Label>" \
  --application-id=com.idachev.<segment> \
  --namespace=com.idachev.<segment> \
  --output="$HOME/develop/personal/<repo-name>" \
  empty-activity
```

Always pass `--output`: without it the CLI writes into the current directory,
which may be another repo. Without `--application-id` and `--namespace` the
template uses `com.example.<name>`, which is wrong for Ivan's apps.

## 2. Copy the conventions, not the code

The reference projects are `~/develop/personal/financy` and
`~/develop/personal/meet-no-miss`. Take only the conventions from them, never
their feature code:

1. `build-project.sh` — unit tests + debug APK, full output in a timestamped
   log under `./tmp/claude-logs/`.
2. `scripts/deploy-apk.sh` (from meet-no-miss; if the file is not there, stop
   and ask — do not invent it) — copies the debug APK to
   `~/Dropbox/mobile/idachev/<repo-name>/` as
   `<repo-name>-debug-<YYYYMMDD>-<HHMM>.apk`,
   moves older APKs to `old/` first, and opens the folder in Finder so Dropbox
   syncs it. Only `~/Dropbox/mobile/idachev/` reaches Ivan's phone. Replace
   `meet-no-miss` inside the copied script with `<repo-name>`.
3. A new `CLAUDE.md` in Bulgarian, written for this app, with its build,
   deploy, language and verification rules. Do not copy another app's file.
4. A new `docs/CONTEXT.md` — the ubiquitous-language glossary for this app;
   code names come from it.
5. Manual dependency injection through an `AppContainer`. No Hilt.
6. Debug-only builds. Add a release build only when Ivan asks. The debug key's
   fingerprint is what gets registered for Google or Microsoft login, so a
   different key breaks login.

Do not change the template's versions (AGP, Gradle, Kotlin, Compose BOM) without
a reason.
