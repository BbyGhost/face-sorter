import hashlib, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
BASE = "https://raw.githubusercontent.com/BbyGhost/face-sorter/main/"
SKIP_DIRS = {".git", ".venv", ".venv311", "node_modules", "__pycache__", ".update-backup"}
SKIP_FILES = {"update-manifest.json", "facesorter.db", "scan.db"}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

items = []
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for name in files:
        if name in SKIP_FILES or name.endswith(".pyc"):
            continue
        p = Path(root) / name
        rel = p.relative_to(ROOT).as_posix()
        items.append({
            "path": rel,
            "sha256": sha256(p),
            "url": BASE + rel
        })

manifest = {"version": VERSION, "notes": "Incremental update", "files": sorted(items, key=lambda x: x["path"])}
(ROOT / "update-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Generated {len(items)} file entries.")
