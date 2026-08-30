# Face Sorter

Privacy-first Windows desktop starter for organizing photo libraries by face. It includes an Electron/React dashboard and a local Python indexing service. No photos are sent to a cloud service.

## Run the desktop app

1. Install Node.js 20+ and Python 3.11+.
2. Run `npm install`, then `npm run dev`.
3. In a second terminal, create a virtual environment, install `backend/requirements.txt`, and run `python backend/service.py`.

## Current scope

The backend safely tracks changed image files in SQLite. Integrating a face-embedding model, identity clustering, thumbnail pipeline, export flow, person merge/split operations, and signed auto-update publishing are deliberately next steps: each needs model licensing, update hosting, and UX decisions before it should be production-enabled.

## Project structure

- `src/` — React dashboard
- `electron/` — desktop process and safe folder picker bridge
- `backend/` — local API and incremental SQLite index


## Automatic incremental updates

See UPDATE.md. The desktop app includes **Check for updates** and downloads only changed files. Configure `update_config.json` with your hosted `update.json` URL.
