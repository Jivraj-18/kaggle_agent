# Google Drive Archive

Use Google Drive for local state/data/artifacts that should not live in Git.

Code and lightweight docs live in GitHub. Mutable Kaggle memory, downloaded data, notebook outputs, submission files, logs, and long-running experiment archives live locally first and are copied to Google Drive when they need to survive beyond this machine.

## Folder

- Name: `kaggle_agent`
- Folder ID: `1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x`
- URL: https://drive.google.com/drive/folders/1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x
- Created: `2026-07-07T11:34:42.263Z`
- Account: `jivibd@gmail.com`

## Sync

The repo uses `gws` for Drive access and `config/drive.json` for the archive folder.

Push changed files:

```bash
python -m kaggle_agent.cli drive-sync push --json
```

Push a specific root:

```bash
python -m kaggle_agent.cli drive-sync push --root state --json
```

The sync stores file hashes and Drive IDs in ignored local state:

```text
state/drive_manifest.json
```

It uploads new files, updates changed files, skips unchanged files, and never deletes remote files.

## Agent Rules

- Do not commit `state/` to Git.
- Do not commit competition data, notebook outputs, submissions, or logs to Git.
- Never delete past local or Drive history unless the user explicitly asks.
- Prefer raw files over zip archives.
- Future agents should read Git for code and Google Drive for archived state/data.
