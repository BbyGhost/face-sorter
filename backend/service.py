"""Local-first face organizer engine with GPU-aware parallel scanning."""
from __future__ import annotations
import hashlib, shutil, sqlite3, threading, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
try:
    from insightface.app import FaceAnalysis
    import onnxruntime as ort
except ImportError:
    FaceAnalysis = None
    ort = None
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'
DATA.mkdir(exist_ok=True)
DB=sqlite3.connect(DATA/'index.sqlite', check_same_thread=False)
DB.execute('CREATE TABLE IF NOT EXISTS images(path TEXT PRIMARY KEY, modified_ns INTEGER,digest TEXT,scanned_at TEXT)')
DB.execute('CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY,name TEXT UNIQUE,embedding BLOB,photos INTEGER DEFAULT 0)')
DB.execute('CREATE TABLE IF NOT EXISTS faces(image_path TEXT,person_id INTEGER,PRIMARY KEY(image_path,person_id))')
DB.execute('CREATE TABLE IF NOT EXISTS face_processed(image_path TEXT PRIMARY KEY)')
DB.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)')
DB.commit()

LOCK=threading.Lock()
DB_LOCK=threading.RLock()
STATE={
    'state':'ready','message':'Choose a folder to begin.','total':0,'processed':0,
    'new':0,'unchanged':0,'failed':0,'faces':0,'speed':0.0,'eta_seconds':None,
    'provider':'','workers':0
}
EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
MODEL_VERSION='arcface-buffalo-l-v2-strict-fast-v2'
FACE_APP=None
FACE_LOCK=threading.Lock()
cv2.setLogLevel(0)
app=FastAPI(docs_url=None,redoc_url=None)

class ScanRequest(BaseModel): folder:str
class ExportRequest(BaseModel): output_folder:str

def safe_folder_name(name:str):
    return ''.join('_' if char in '<>:"/\\|?*' else char for char in name).strip('. ') or 'Unnamed person'

def copy_to_folder(paths, folder:Path):
    folder.mkdir(parents=True,exist_ok=True); count=0
    for raw in paths:
        src=Path(raw)
        if not src.exists(): continue
        target=folder/src.name
        if target.exists():
            target=folder/f'{src.stem}_{hashlib.sha1(str(src).encode()).hexdigest()[:8]}{src.suffix}'
        shutil.copy2(src,target); count+=1
    return count

def prepare_model():
    global FACE_APP
    if FaceAnalysis is None:
        raise RuntimeError('Face model is not installed. Run pip install -r backend\\requirements.txt.')
    with FACE_LOCK:
        if FACE_APP is None:
            available=ort.get_available_providers() if ort else []
            if 'DmlExecutionProvider' in available:
                providers=['DmlExecutionProvider','CPUExecutionProvider']
            elif 'CUDAExecutionProvider' in available:
                providers=['CUDAExecutionProvider','CPUExecutionProvider']
            else:
                providers=['CPUExecutionProvider']
            FACE_APP=FaceAnalysis(name='buffalo_l',providers=providers)
            # 320 keeps detection fast while retaining the full-resolution originals.
            FACE_APP.prepare(ctx_id=-1,det_size=(320,320))
            with LOCK:
                STATE['provider']='DML GPU' if 'DmlExecutionProvider' in providers else (
                    'CUDA GPU' if 'CUDAExecutionProvider' in providers else 'CPU')
    return FACE_APP

def migrate_model_index():
    with DB_LOCK:
        row=DB.execute('SELECT value FROM settings WHERE key=?',('face_model',)).fetchone()
        if row and row[0]==MODEL_VERSION: return
        DB.execute('DELETE FROM faces')
        DB.execute('DELETE FROM face_processed')
        DB.execute('DELETE FROM people')
        DB.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                   ('face_model',MODEL_VERSION))
        DB.commit()

def descriptors(file:Path):
    """Decode once, temporarily resize only the in-memory analysis image, then infer."""
    try:
        raw=np.fromfile(str(file),dtype=np.uint8)
        image=cv2.imdecode(raw,cv2.IMREAD_COLOR)
        if image is None: return []
        height,width=image.shape[:2]
        largest=max(height,width)
        if largest>1600:
            scale=1600/largest
            image=cv2.resize(image,(round(width*scale),round(height*scale)),
                             interpolation=cv2.INTER_AREA)
        faces=prepare_model().get(image)
        result=[]
        for face in faces:
            emb=np.asarray(face.embedding,dtype=np.float32)
            emb/=np.linalg.norm(emb)+1e-8
            result.append(emb)
        return result
    except (OSError,ValueError,cv2.error):
        return []

def load_people_state():
    """Load matching vectors once; never query SQLite for every detected face."""
    people={}
    with DB_LOCK:
        rows=DB.execute('SELECT id,name,embedding,photos FROM people').fetchall()
    for ident,name,raw,photos in rows:
        if raw:
            vec=np.frombuffer(raw,dtype=np.float32).copy()
            vec/=np.linalg.norm(vec)+1e-8
            people[int(ident)]={'name':name,'embedding':vec,'photos':int(photos or 0)}
    return people

def match_and_update(vector, people):
    """Fast in-memory cosine matching. Returns a person id."""
    if not people:
        with DB_LOCK:
            number=DB.execute('SELECT COALESCE(MAX(id),0)+1 FROM people').fetchone()[0]
            cursor=DB.execute('INSERT INTO people(name,embedding,photos) VALUES(?,?,0)',
                              (f'Person {number}',vector.astype(np.float32).tobytes()))
            ident=cursor.lastrowid
        people[ident]={'name':f'Person {number}','embedding':vector.copy(),'photos':0}
        return ident

    ids=list(people)
    matrix=np.stack([people[i]['embedding'] for i in ids],axis=0)
    scores=matrix @ vector
    idx=int(np.argmax(scores))
    score=float(scores[idx])
    if score>=0.58:
        ident=ids[idx]
        p=people[ident]
        count=p['photos']
        updated=(p['embedding']*count+vector)/(count+1)
        updated/=np.linalg.norm(updated)+1e-8
        p['embedding']=updated
        p['photos']=count+1
        return ident

    with DB_LOCK:
        max_id=DB.execute('SELECT COALESCE(MAX(id),0) FROM people').fetchone()[0]
        ident=int(max_id)+1
        name=f'Person {ident}'
        DB.execute('INSERT INTO people(id,name,embedding,photos) VALUES(?,?,?,0)',
                   (ident,name,vector.astype(np.float32).tobytes()))
    people[ident]={'name':name,'embedding':vector.copy(),'photos':0}
    return ident

def refresh_person_counts(people):
    with DB_LOCK:
        for ident,p in people.items():
            DB.execute('UPDATE people SET embedding=?,photos=? WHERE id=?',
                       (p['embedding'].astype(np.float32).tobytes(),p['photos'],ident))
        DB.commit()

def _existing_index():
    """One DB read instead of two SQLite queries for every photo."""
    with DB_LOCK:
        return {row[0]: (row[1],row[2]) for row in
                DB.execute('SELECT path,modified_ns,1 FROM images').fetchall()}

def _process_one(file:Path):
    try:
        stat=file.stat()
        vectors=descriptors(file)
        return file,stat,vectors,True
    except (OSError,PermissionError):
        return file,None,[],False

def scan(folder):
    start=time.perf_counter()
    try:
        with LOCK:
            STATE.update(state='scanning',message='Loading GPU face model…',total=0,
                         processed=0,new=0,unchanged=0,failed=0,faces=0,speed=0.0,eta_seconds=None)
        migrate_model_index()
        prepare_model()
    except Exception as error:
        with LOCK: STATE.update(state='error',message=f'Face model could not start: {error}')
        return

    files=[p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXT]
    existing=_existing_index()
    people=load_people_state()
    # 2 concurrent inference workers is a safe DirectML starting point; CPU gets more.
    provider=STATE.get('provider','')
    workers=2 if provider=='DML GPU' else max(2,min(6,(os.cpu_count() or 4)//2))
    with LOCK:
        STATE.update(total=len(files),processed=0,new=0,unchanged=0,failed=0,faces=0,
                     workers=workers,message=f'Scanning with {provider}, {workers} workers…')
    pending_faces=[]
    pending_images=[]
    completed=0

    def commit_pending():
        nonlocal pending_faces,pending_images
        if not pending_faces and not pending_images: return
        with DB_LOCK:
            if pending_faces:
                DB.executemany('INSERT OR REPLACE INTO faces(image_path,person_id) VALUES(?,?)',pending_faces)
            if pending_images:
                DB.executemany('INSERT OR REPLACE INTO face_processed(image_path) VALUES(?)',
                               [(p,) for p in pending_images])
                now=datetime.now(timezone.utc).isoformat()
                DB.executemany('INSERT OR REPLACE INTO images(path,modified_ns,digest,scanned_at) VALUES(?,?,?,?)',
                               [(str(p),st, '', now) for p,st in pending_images_meta])
            DB.commit()
        pending_faces.clear(); pending_images.clear()

    # Submit in bounded chunks so a 73k library doesn't create 73k live futures.
    CHUNK=64
    try:
        with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='face-scan') as pool:
            for offset in range(0,len(files),CHUNK):
                chunk=files[offset:offset+CHUNK]
                futures={pool.submit(_process_one,p):p for p in chunk}
                pending_images_meta=[]
                for future in as_completed(futures):
                    file=futures[future]
                    try: file,stat,vectors,ok=future.result()
                    except Exception:
                        stat=None;vectors=[];ok=False
                    completed+=1
                    if not ok or stat is None:
                        with LOCK:
                            STATE['processed']=completed; STATE['failed']+=1
                    else:
                        key=str(file)
                        old=existing.get(key)
                        if old and old[0]==stat.st_mtime_ns:
                            with LOCK:
                                STATE['processed']=completed; STATE['unchanged']+=1
                        else:
                            # Remove stale assignments before inserting fresh detections.
                            with DB_LOCK:
                                DB.execute('DELETE FROM faces WHERE image_path=?',(key,))
                            for vector in vectors:
                                ident=match_and_update(vector,people)
                                pending_faces.append((key,ident))
                            pending_images.append(key)
                            pending_images_meta.append((key,stat.st_mtime_ns))
                            with LOCK:
                                STATE['processed']=completed; STATE['new']+=1; STATE['faces']+=len(vectors)
                    elapsed=max(time.perf_counter()-start,0.001)
                    speed=completed/elapsed
                    remaining=max(len(files)-completed,0)
                    eta=remaining/speed if speed>0 else None
                    with LOCK:
                        STATE['speed']=speed; STATE['eta_seconds']=eta
                # One transaction per 64 images instead of one per image.
                if pending_images:
                    with DB_LOCK:
                        if pending_faces:
                            DB.executemany('INSERT OR REPLACE INTO faces(image_path,person_id) VALUES(?,?)',pending_faces)
                        DB.executemany('INSERT OR REPLACE INTO face_processed(image_path) VALUES(?)',
                                       [(p,) for p in pending_images])
                        now=datetime.now(timezone.utc).isoformat()
                        DB.executemany('INSERT OR REPLACE INTO images(path,modified_ns,digest,scanned_at) VALUES(?,?,?,?)',
                                       [(p,st,'',now) for p,st in pending_images_meta])
                        DB.commit()
                    pending_faces.clear();pending_images.clear();pending_images_meta.clear()
                # Persist in-memory centroids periodically.
                refresh_person_counts(people)
    finally:
        refresh_person_counts(people)

    with DB_LOCK:
        DB.execute('DELETE FROM people WHERE photos=0')
        DB.commit()
    elapsed=max(time.perf_counter()-start,0.001)
    with LOCK:
        STATE.update(state='complete',message=f'Face scan complete — {completed:,} photos processed.',
                     speed=completed/elapsed,eta_seconds=0)

@app.get('/')
def home(): return FileResponse(ROOT/'web'/'index.html')

@app.get('/api/status')
def status():
    with LOCK: return dict(STATE)

@app.post('/api/scan')
def start(request:ScanRequest):
    folder=Path(request.folder.strip().strip('"')).expanduser()
    if not folder.is_dir(): raise HTTPException(400,'That folder does not exist.')
    with LOCK:
        if STATE['state']=='scanning': raise HTTPException(409,'A scan is already running.')
    threading.Thread(target=scan,args=(folder.resolve(),),daemon=True).start()
    return {'ok':True}

@app.get('/api/people')
def people():
    with DB_LOCK:
        rows=DB.execute('SELECT id,name,photos FROM people ORDER BY photos DESC,name').fetchall()
    return [{'id':x[0],'name':x[1],'photos':x[2]} for x in rows]

def person_images(person_id:int):
    with DB_LOCK:
        return [row[0] for row in DB.execute(
            'SELECT image_path FROM faces WHERE person_id=? ORDER BY image_path',(person_id,)).fetchall()]

def export_person(person_id:int, output_folder:str):
    output=Path(output_folder)
    if not output_folder.strip(): raise ValueError('Choose an output folder.')
    with DB_LOCK:
        row=DB.execute('SELECT name FROM people WHERE id=?',(person_id,)).fetchone()
        paths=[item[0] for item in DB.execute('SELECT image_path FROM faces WHERE person_id=?',(person_id,)).fetchall()]
    if not row: raise ValueError('That person group no longer exists.')
    folder=output/safe_folder_name(row[0])
    return {'copied':copy_to_folder(paths,folder),'folder':str(folder)}

def export_all_people(output_folder:str):
    if not output_folder.strip(): raise ValueError('Choose an output folder.')
    with DB_LOCK: groups=DB.execute('SELECT id,name FROM people').fetchall()
    total=0
    for person_id,_name in groups: total+=export_person(person_id,output_folder)['copied']
    return {'copied':total,'groups':len(groups),'folder':str(Path(output_folder))}

def reset_library():
    with LOCK:
        if STATE['state']=='scanning': raise ValueError('Wait for the current scan to finish before resetting.')
    with DB_LOCK:
        DB.execute('DELETE FROM faces');DB.execute('DELETE FROM face_processed')
        DB.execute('DELETE FROM people');DB.execute('DELETE FROM images');DB.commit()
    with LOCK: STATE.update(state='ready',message='Library cleared. Choose a folder to scan.',
                            total=0,processed=0,new=0,unchanged=0,failed=0,faces=0,speed=0.0,eta_seconds=None)

@app.post('/api/people/{person_id}/rename')
def rename(person_id:int,body:dict):
    name=str(body.get('name','')).strip()
    if not name: raise HTTPException(400,'Enter a name.')
    try:
        with DB_LOCK:
            DB.execute('UPDATE people SET name=? WHERE id=?',(name,person_id));DB.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400,'That name is already used.')
    return {'ok':True}

@app.post('/api/export-unknown')
def export(request:ExportRequest):
    if not request.output_folder.strip(): raise HTTPException(400,'Choose an output folder.')
    out=Path(request.output_folder.strip().strip('"')).expanduser()/'Unknown'
    with DB_LOCK:
        paths=DB.execute('SELECT path FROM images WHERE path NOT IN (SELECT image_path FROM faces)').fetchall()
    count=copy_to_folder([row[0] for row in paths],out)
    return {'copied':count,'folder':str(out)}

if __name__=='__main__':
    import uvicorn
    print('Face Sorter engine ready')
    uvicorn.run(app,host='127.0.0.1',port=8765)
