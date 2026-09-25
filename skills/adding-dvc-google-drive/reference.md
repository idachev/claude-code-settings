# DVC + Google Drive: full setup reference

Companion to SKILL.md. Written against DVC 3.67. Example repo: `sensor-lab`, binaries in `data/raw/<site>/<capture>.bin`, hand-edited sidecars in `data/meta/<site>/<capture>.json` (split tree).

## 1. Google Cloud: OAuth client (once per team)

DVC's built-in Google app is blocked (`This app is blocked`). Create your own:

1. Google Cloud Console → new project for the repo.
2. APIs & Services → enable **Google Drive API**.
3. OAuth consent screen: **Internal** for Google Workspace. Otherwise External + Testing, and add every teammate's email as a Test user (tokens expire after 7 days in Testing mode; Internal has no such limit).
4. Credentials → Create credentials → OAuth client ID → **Desktop app**.
5. Copy client ID and client secret into a password manager. Share with teammates out of band. Never in Git, never in a chat that is archived.

## 2. Google Drive: storage folder (once per team)

1. In a **Shared Drive**, create a folder, e.g. `sensor-lab-dvc`, and inside it the subfolder `dvcstore`. DVC will not create `dvcstore`; a missing subfolder fails at first push.
2. Share the Shared Drive with named people or a Google Group. Viewer is enough for `dvc pull`; Contributor or above for `dvc push`. Do not use "Anyone with the link".
3. Open the **parent** folder (`sensor-lab-dvc`, not `dvcstore`). Folder ID = last path segment of `https://drive.google.com/drive/folders/<FOLDER_ID>`. The remote URL is `gdrive://<FOLDER_ID>/dvcstore`.

## 3. Repo, first time

```bash
pip install "dvc[gdrive]"            # or: uv add "dvc[gdrive]"
dvc init
dvc remote add -d gdrive gdrive://<FOLDER_ID>/dvcstore
dvc remote modify gdrive gdrive_trash_only true
dvc remote modify gdrive gdrive_acknowledge_abuse true   # optional: lets pull fetch files Drive flags
git add .dvc/config .dvc/.gitignore .dvcignore
git commit -m "dvc: google drive remote"
```

Then lay out the tree **before** the first `dvc add`. Move sidecars out of the data directory with `git mv` so history and PR diffs show a rename:

```bash
mkdir -p data/meta
for f in data/raw/*/*.meta.json; do
  d=data/meta/$(basename "$(dirname "$f")"); mkdir -p "$d"; git mv "$f" "$d/"
done
git commit -m "meta: split sidecars out of data/raw"
```

If binaries were ever committed, take them out of the index first (files stay on disk):

```bash
git rm -r --cached data/raw
git commit -m "raw: stop tracking binaries in git"
```

Old blobs remain in history. To shrink the clone, rewrite with `git filter-repo --path data/raw --invert-paths` and force-push, after the team agrees. Then:

```bash
dvc add data/raw                     # writes data/raw.dvc and /raw into data/.gitignore
git add data/raw.dvc data/.gitignore
git commit -m "raw: first capture set"
```

Add the safety-net globs from SKILL.md to the root `.gitignore` in the same commit.

## 4. Repo, every machine

```bash
git clone <url> && cd sensor-lab
pip install "dvc[gdrive]"
dvc remote modify --local gdrive gdrive_client_id '<client-id>'
dvc remote modify --local gdrive gdrive_client_secret '<client-secret>'
dvc pull                             # first run opens a browser; log in with an account that sees the folder
```

`--local` writes `.dvc/config.local` (gitignored). Verify with `dvc config -l --local`. The user token is cached at `~/Library/Caches/pydrive2fs/<client_id>/default.json` on macOS (`~/.cache/pydrive2fs/...` on Linux). If a refresh token dies, delete that file and pull again.

Pre-commit guard (also fine as a git hook):

```bash
git diff --cached .dvc/config | grep gdrive_client_ && echo "STOP: credentials in .dvc/config"
```

## 5. Daily flow

Change or add a capture:

```bash
# put/replace the file at data/raw/<site>/<capture>.bin
dvc add data/raw
git add data/raw.dvc
git commit -m "raw: <site>/<capture>"
dvc push                             # bytes to Drive, only new objects
git push                             # pointer to Git; always after dvc push
```

Edit a sidecar: plain Git, no `dvc add`.

Subset for an experiment, same bytes:

```bash
mkdir -p experiments/night-runs                       # import does not create the parent dir; without it: "stage working dir ... does not exist"
dvc import . data/raw -o experiments/night-runs/raw   # experiments/night-runs/raw.dvc, same md5
git add experiments/night-runs/raw.dvc experiments/night-runs/.gitignore   # import writes /raw there
# experiments/night-runs/manifest.jsonl in Git lists which captures the experiment uses
```

Derived files with new bytes (crops, downsamples) get their own DVC path, e.g. `experiments/night-runs/crops/`.

New DVC-tracked directory: `dvc add data/<name>` appends `/<name>` to `data/.gitignore`. Commit that file too.

## 5a. Rehearsal without Drive (agents, offline machines)

Remote commands with no cached token open a browser and hang. To prove clone + pull and the push-before-git-push order before credentials exist, add a throwaway filesystem remote that never enters `.dvc/config`:

```bash
dvc remote add --local sim /tmp/sim-store
dvc push -r sim
git clone . /tmp/sim-clone && cd /tmp/sim-clone
dvc remote add --local sim /tmp/sim-store
dvc pull -r sim
```

Delete the `sim` lines from `.dvc/config.local` afterwards.

## 6. CI (GitHub Actions)

User OAuth cannot run headless. Use a service account:

1. Cloud Console → IAM → Service Accounts → create, then Keys → JSON.
2. Share the Shared Drive with the service account email (`...@<project>.iam.gserviceaccount.com`). Without this it authenticates and then sees nothing.
3. Store the JSON as a repo secret, e.g. `GDRIVE_CREDENTIALS_DATA`.

```yaml
- run: pip install "dvc[gdrive]"
- run: dvc remote modify --local gdrive gdrive_use_service_account true
- run: dvc pull
  env:
    GDRIVE_CREDENTIALS_DATA: ${{ secrets.GDRIVE_CREDENTIALS_DATA }}
```

Locally the same mode is `dvc remote modify --local gdrive gdrive_service_account_json_file_path path/to/key.json`. Client id/secret are not needed in service-account mode.

Optional: cache `.dvc/cache` with `actions/cache` keyed on `hashFiles('**/*.dvc')` to skip repeat pulls.

## 7. Disk space

`du` shows the cache and the workspace at full size each. With the default `cache.type = reflink,copy` on APFS, btrfs or XFS the workspace file is a copy-on-write clone of the cache object, so the bytes exist once. `dvc doctor` prints the supported link types. `dvc checkout --relink` re-creates clones if some files were copied. Only on filesystems without reflink (ext4) is `dvc config --local cache.type hardlink,copy` worth it, and then edits need `dvc unprotect <path>` first.

## 8. Limits and gotchas

- Drive API quota is per GCP project. Heavy traffic needs a quota raise.
- `dvc pull` rehashes what it downloads; Drive is not a trusted remote. Large pulls are slow.
- Shared Drives have their own upload limits and file-count limits (400k items per Shared Drive).
- `dvc gc` deletes unreferenced objects. With `gdrive_trash_only = true` they go to Drive trash instead of vanishing.
- Drive UI shows hashed object names, not the original paths. It is a store, not a gallery.
- Non-ASCII directory names: keep NFC everywhere. macOS `core.precomposeunicode = true` (Apple Git default) makes Git store NFC.
- Do not `dvc add` the same bytes under two paths unless a tool needs the full tree on disk; if you do, record the second path in a manifest in Git so the duplication is deliberate. Drive still stores one object.

## 9. Alternatives rejected

| Option | Why not |
|---|---|
| Git blobs for binaries | History bloat; GitHub 100 MB per-file limit. |
| Git LFS on GitHub | Bandwidth/storage quotas; not Drive. |
| Git LFS custom transfer agent to Drive | Agent on every machine; not native. |
| git-annex + rclone | Works, including readable names in Drive via `exporttree`; heavier daily UX. |
