# Updating Face Sorter

Repository:
https://github.com/BbyGhost/face-sorter

## Normal workflow

1. Fix the bug in the source.
2. Change `APP_VERSION` in `updater.py`.
3. Run the manifest generator:
   `python tools/make_update_manifest.py`
4. Commit and push the changed files to `main`.

Installed copies of Face Sorter can then compare their local file hashes with
`update-manifest.json` and download only changed files.

## Important

Do not commit `.venv`, `.venv311`, `node_modules`, local databases, caches,
or your personal photo library.
