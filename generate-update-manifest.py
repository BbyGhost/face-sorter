"""Generate update.json for the incremental updater.
Usage: python generate-update-manifest.py 0.2.1 https://raw.githubusercontent.com/OWNER/REPO/main
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
version=sys.argv[1] if len(sys.argv)>1 else "0.2.0"
base=sys.argv[2].rstrip("/") if len(sys.argv)>2 else ""
exclude={"update.json", ".update-backup", "data", ".venv", ".venv311", "node_modules", "__pycache__", "outputs", "work"}
files=[]
for p in ROOT.rglob('*'):
    if not p.is_file(): continue
    rel=p.relative_to(ROOT).as_posix()
    if any(part in exclude for part in p.relative_to(ROOT).parts): continue
    if rel.endswith('.pyc'): continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    files.append({"path":rel,"sha256":h})
files.sort(key=lambda x:x['path'])
manifest={"version":version,"base_url":base,"files":files}
(ROOT/'update.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(f"Wrote update.json for v{version} with {len(files)} files")
