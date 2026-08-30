import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

APP_VERSION = "1.0.0"
UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/BbyGhost/face-sorter/main/update-manifest.json"
)
APP_DIR = Path(__file__).resolve().parent

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def check_for_updates():
    manifest = download_json(UPDATE_MANIFEST_URL)
    remote_version = manifest.get("version", APP_VERSION)
    if remote_version == APP_VERSION:
        return {"available": False, "version": APP_VERSION}

    changed = []
    for item in manifest.get("files", []):
        rel = Path(item["path"])
        local = APP_DIR / rel
        if not local.exists() or sha256(local) != item["sha256"]:
            changed.append(item)

    return {
        "available": bool(changed),
        "version": remote_version,
        "changed_files": changed,
        "manifest": manifest,
    }

def install_updates(info):
    if not info.get("available"):
        return False

    backup = APP_DIR / ".update-backup"
    backup.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        for item in info["changed_files"]:
            rel = Path(item["path"])
            url = item["url"]
            target = APP_DIR / rel
            target.parent.mkdir(parents=True, exist_ok=True)

            temp = Path(td) / rel
            temp.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=60) as r, temp.open("wb") as f:
                shutil.copyfileobj(r, f)

            if sha256(temp) != item["sha256"]:
                raise RuntimeError(f"Checksum verification failed: {rel}")

            if target.exists():
                backup_target = backup / rel
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_target)

            shutil.copy2(temp, target)

    # The current launcher can simply be restarted by the UI after this returns.
    return True

if __name__ == "__main__":
    info = check_for_updates()
    print(json.dumps({
        "available": info.get("available", False),
        "version": info.get("version", APP_VERSION),
        "changed": [x["path"] for x in info.get("changed_files", [])],
    }, indent=2))
