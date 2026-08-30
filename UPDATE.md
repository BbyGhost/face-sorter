# Incremental updater

Face Sorter can update only changed program files. It does **not** require downloading the whole application again.

## One-time setup

1. Put this project in a GitHub repository (or another HTTPS file host).
2. Make the repository's raw-file base URL the value of `manifest_url` in `update_config.json` for the `update.json` file.
   Example:
   `https://raw.githubusercontent.com/OWNER/REPO/main/update.json`
3. Generate the manifest whenever you publish a new version:
   `python generate-update-manifest.py 0.2.1 https://raw.githubusercontent.com/OWNER/REPO/main`
4. Commit and push the changed files and `update.json`.

## Publishing a fix

Change the broken source file, increment the version, regenerate `update.json`, and push. Users can then click **Check for updates**. The updater compares SHA-256 hashes and downloads only changed files, verifies them, backs up replaced files, applies the update, and restarts the app.

Do not put secrets, API keys, Python virtual environments, `node_modules`, photo libraries, or the SQLite database in the update repository.
