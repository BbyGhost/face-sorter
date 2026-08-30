import json, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

APP_VERSION="1.1.0"
UPDATE_MANIFEST_URL="https://raw.githubusercontent.com/BbyGhost/face-sorter/main/update-manifest.json"
APP_DIR=Path(__file__).resolve().parent

def download_json(url):
    with urllib.request.urlopen(url,timeout=15) as r:return json.loads(r.read().decode("utf-8"))

def check():
    manifest=download_json(UPDATE_MANIFEST_URL)
    remote=str(manifest.get("version",APP_VERSION))
    changed=[]
    if remote!=APP_VERSION:
        for item in manifest.get("files",[]):
            local=APP_DIR/Path(item["path"])
            changed.append(item) if not local.exists() else None
        if not changed:
            changed=list(manifest.get("files",[]))
    return {"update":remote!=APP_VERSION and bool(changed),"current":APP_VERSION,"remote":remote,"changed":changed,"manifest":manifest}

def apply(result):
    changed=result.get("changed",[])
    if not changed:return False
    backup=APP_DIR/".update-backup"; backup.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        for item in changed:
            rel=Path(item["path"]); target=APP_DIR/rel; target.parent.mkdir(parents=True,exist_ok=True)
            temp=Path(td)/rel; temp.parent.mkdir(parents=True,exist_ok=True)
            with urllib.request.urlopen(item["url"],timeout=60) as r,temp.open("wb") as f: shutil.copyfileobj(r,f)
            if item.get("sha256"):
                import hashlib
                h=hashlib.sha256()
                with temp.open("rb") as f:
                    for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
                if h.hexdigest()!=item["sha256"]:raise RuntimeError(f"Checksum verification failed: {rel}")
            if target.exists():
                b=backup/rel; b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,b)
            shutil.copy2(temp,target)
    return True

def restart():
    subprocess.Popen([sys.executable,str(APP_DIR/"desktop.py")],cwd=str(APP_DIR),creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))

if __name__=="__main__": print(json.dumps(check(),indent=2))
