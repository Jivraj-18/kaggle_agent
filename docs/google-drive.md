# Google Drive Archive

Use Google Drive for local state/data/artifact archives that should not live in Git.

Code and lightweight docs live in GitHub. Mutable Kaggle memory, downloaded data, notebook outputs, submission files, logs, and long-running experiment archives should be copied to Google Drive when they need to be preserved outside this machine.

## Folder

- Name: `kaggle_agent`
- Folder ID: `1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x`
- URL: https://drive.google.com/drive/folders/1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x
- Created: `2026-07-07T11:34:42.263Z`

## CLI

Authenticated tool:

```bash
gws
```

List archive folder metadata:

```bash
gws drive files get --params '{"fileId":"1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x","fields":"id,name,webViewLink,mimeType,createdTime"}'
```

Upload an archive file into the folder:

```bash
gws drive +upload --upload path/to/archive.zip \
  --json '{"name":"archive.zip","parents":["1SOZL5T00dVthyWae5TEAQAhh2LGbjr4x"]}'
```

## Agent Rules

- Do not commit `state/` to Git.
- Do not commit competition data, notebook outputs, submissions, or logs to Git.
- Never delete past local or Drive history unless the user explicitly asks.
- Prefer append-only archives with timestamps.
- Future agents should read Git for code and Google Drive for archived state/data.
