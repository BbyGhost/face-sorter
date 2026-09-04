import hashlib, json, os, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

APP_VERSION="3.3.0"
UPDATE_MANIFEST_URL="https://raw.githubusercontent.com/BbyGhost/face-sorter/main/update-manifest.json"
APP_DIR=Path(__file__).resolve().parent
BACKUP_DIR=APP_DIR/".update-backup"

def download_bytes(url,timeout=30):
    req=urllib.request.Request(url,headers={"Cache-Control":"no-cache","User-Agent":"FaceSorter-Updater"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def check():
    manifest=download_bytes(UPDATE_MANIFEST_URL,15)
    data=json.loads(manifest.decode("utf-8"))
    remote=str(data.get("version",APP_VERSION))
    changed=[]
    for item in data.get("files",[]):
        target=APP_DIR/Path(item["path"])
        if not target.exists(): changed.append(item); continue
        expected=item.get("sha256")
        if expected:
            h=hashlib.sha256(target.read_bytes()).hexdigest()
            if h.lower()!=str(expected).lower(): changed.append(item)
        else: changed.append(item)
    return {"update":remote!=APP_VERSION and bool(changed),"current":APP_VERSION,"remote":remote,"changed":changed,"manifest":data}

def apply(result):
    changed=result.get("changed",[])
    if not changed:return False
    BACKUP_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="facesorter-update-") as td:
        downloaded=[]
        for item in changed:
            rel=Path(item["path"]); temp=Path(td)/rel; temp.parent.mkdir(parents=True,exist_ok=True)
            data=download_bytes(item["url"],60)
            expected=item.get("sha256")
            if expected and hashlib.sha256(data).hexdigest().lower()!=str(expected).lower():
                raise RuntimeError(f"Checksum verification failed: {rel}")
            temp.write_bytes(data); downloaded.append((item,temp))
        for item,temp in downloaded:
            rel=Path(item["path"]); target=APP_DIR/rel
            if target.exists():
                backup=BACKUP_DIR/rel; backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
            target.parent.mkdir(parents=True,exist_ok=True); os.replace(str(temp),str(target))
    return True

def restart():
    launcher=APP_DIR/"launcher.py"
    target=launcher if launcher.exists() else APP_DIR/"desktop.py"
    subprocess.Popen([sys.executable,str(target)],cwd=str(APP_DIR),creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),close_fds=True)

if __name__=="__main__":print(json.dumps(check(),indent=2))
