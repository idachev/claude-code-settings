---
name: adding-dvc-google-drive
description: Use when a Git repo must keep large binaries (scans, captures, models, datasets) out of Git blobs with a Google Drive remote via DVC, when hand-edited sidecar files must stay reviewable in Git next to DVC data, or when setting up dvc pull for teammates and CI. Also use when `dvc add` says "already tracked by SCM", when DVC + Drive credentials are about to be committed, when a first `dvc push`/`dvc pull` opens a browser and hangs, or when Google answers "This app is blocked".
---

# Adding DVC with a Google Drive remote

## Overview

Git keeps a small `.dvc` pointer (MD5 + size). DVC keeps the bytes in a local cache and in a Google Drive folder, addressed by hash. `git clone` + `dvc pull` gives a teammate the full tree. Credentials never enter Git.

Decisions that a first attempt gets wrong are below. Full command sequence, Google Cloud steps and CI are in [reference.md](reference.md).

## Decide first: where do sidecar files live?

DVC tracks one directory as one output. If Git tracks **any** file under that directory, `dvc add <dir>` fails:

```text
ERROR: output 'data/raw' is already tracked by SCM (e.g. Git).
```

DVC's only suggestion is `git rm -r --cached`, which drops the sidecars from Git. `.gitignore` negations do not help: the next `dvc add` writes `/raw` into `data/.gitignore` and that line beats every `!pattern`.

| Sidecar count | Layout |
|---|---|
| Up to a few dozen data files | One `.dvc` per data file (`dvc add --glob 'data/raw/*/*.bin'`). Sidecars stay next to data. |
| Hundreds or more | **Split tree.** Data in `data/raw/<site>/<capture>.bin`, sidecars in `data/meta/<site>/<capture>.json`. Same relative path, one `.dvc` for the whole `data/raw`. Code joins them by relative path, not by adjacency. |

Per-file `.dvc` at scale means hundreds of pointer files plus a DVC-written `.gitignore` in every directory. Pick split tree before the first `dvc add`; moving later touches every pointer file and every DVC-written `.gitignore`.

With one `.dvc` per directory, run `dvc add data/raw`. On DVC 3.x `dvc add data/raw/site-a/x.bin` also works and updates the same `data/raw.dvc`; there is no per-file pointer. Use the directory form so nobody expects one. DVC rehashes only changed files.

**Binaries already committed to Git?** `git rm -r --cached data/raw` before the first `dvc add`, and move sidecars with `git mv` so PRs show renames. Steps and the `git filter-repo` option are in reference.md §3.

## Quick reference

| Want | Command |
|---|---|
| Fetch data after clone | `dvc pull` |
| Record a changed or new file | put it on its path → `dvc add data/raw` → `git add data/raw.dvc` → `git commit` |
| Publish | `dvc push` **then** `git push` |
| Subset or experiment on same bytes | `mkdir -p experiments/<name>` → `dvc import . data/raw -o experiments/<name>/raw` + a manifest of ids in Git. Never `cp` |
| Check credentials are local | `dvc config -l --local` shows `gdrive_client_*`; `git diff --cached .dvc/config` shows none |
| Rehearse push/clone/pull without Drive | `dvc remote add --local sim /tmp/sim-store` → `dvc push -r sim` → clone → `dvc pull -r sim`. Stays out of `.dvc/config` |

`dvc push` before `git push`: otherwise a teammate's `dvc pull` finds a pointer whose object is not in Drive yet.

## Config that must be in `.dvc/config` (committed)

```ini
['remote "gdrive"']
    url = gdrive://<FOLDER_ID>/dvcstore
    gdrive_trash_only = true
```

- `<FOLDER_ID>` is the ID of the **parent** folder in a Shared Drive, shared with named people or a group. Not `gdrive://root` (every user's own My Drive). Not "Anyone with the link".
- The subfolder named in the URL (`dvcstore`) **must already exist** inside that parent. DVC does not create it. Do not paste the subfolder's own ID.
- `gdrive_trash_only = true`: without it `dvc gc` deletes permanently.

## Config that must stay local

```bash
dvc remote modify --local gdrive gdrive_client_id '<id>'
dvc remote modify --local gdrive gdrive_client_secret '<secret>'
```

`--local` writes `.dvc/config.local` (gitignored by `dvc init`). Without `--local` the secret lands in `.dvc/config` and in Git. DVC's built-in Google app is blocked; each team needs its own GCP OAuth client of type **Desktop app** (see reference.md).

## Safety net in root `.gitignore`

DVC only ignores the exact paths it added. Add globs for **your** data extensions and for secrets so a stray copy never becomes a Git blob (`*.bin`, `*.tif`, `*.pdf` below are examples, replace them):

```gitignore
.dvc/cache
.dvc/tmp
.dvc/config.local
*.bin
*.tif
*.pdf
*credentials*.json
*service-account*.json
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Running `dvc push`/`dvc pull`/`dvc status -c` from an agent session with no cached token | It opens a browser OAuth flow and hangs. The human runs the first remote command in their own terminal. Rehearse with the `--local` filesystem remote from the quick reference. |
| Forgetting the `.gitignore` DVC writes next to a new output | `dvc add data/<name>` and `dvc import ... -o experiments/<name>/raw` each write a `.gitignore` beside the output. Commit it with the `.dvc` file. |
| Committing a `drive.google.com/file/d/...` URL as "the reference" | The reference is the MD5 in the `.dvc` file. Drive shows hashes, not names; local names come from Git paths after `dvc pull`. |
| Switching `cache.type` to `hardlink` to save disk | On APFS/btrfs/XFS the default `reflink,copy` already shares blocks; `du` double-counts but disk does not. Hardlinks make workspace files read-only. Details in reference.md §7. |
| Copying bytes into a second tracked directory for a subset | `dvc import` points at the same hashes; Drive stores one object. A manifest of ids in Git defines the subset. |
| Non-ASCII directory names differ between macOS and Linux | Keep names NFC on disk, in the `.dvc` manifest and in Git. On macOS `core.precomposeunicode = true` (Apple Git default). |
| Hand-editing DVC's generated `.gitignore` | Leave it. Put your own patterns in the root `.gitignore`. |
