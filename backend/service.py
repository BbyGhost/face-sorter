"""Local-first face organizer engine with selectable CPU/GPU scanning."""
from __future__ import annotations
import hashlib, shutil, sqlite3, threading, time, os, queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
try:
    import onnxruntime as ort
    # ORT 1.21+ can preload CUDA/cuDNN DLLs from NVIDIA Python packages.
    # Do this before InsightFace creates any ONNX sessions.
    if hasattr(ort,'preload_dlls'):
        try: ort.preload_dlls(directory="")
        except Exception: pass
    from insightface.app import FaceAnalysis
except ImportError:
    FaceAnalysis=None; ort=None
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parent.parent; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
DB=sqlite3.connect(DATA/'index.sqlite',check_same_thread=False)
DB.execute('CREATE TABLE IF NOT EXISTS images(path TEXT PRIMARY KEY,modified_ns INTEGER,digest TEXT,scanned_at TEXT)')
DB.execute('CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY,name TEXT UNIQUE,embedding BLOB,photos INTEGER DEFAULT 0)')
DB.execute('CREATE TABLE IF NOT EXISTS faces(image_path TEXT,person_id INTEGER,PRIMARY KEY(image_path,person_id))')
DB.execute('CREATE TABLE IF NOT EXISTS face_processed(image_path TEXT PRIMARY KEY)')
DB.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)'); DB.commit()
LOCK=threading.Lock(); DB_LOCK=threading.RLock(); PEOPLE_LOCK=threading.RLock()
STATE={'state':'ready','message':'Choose a folder to begin.','total':0,'processed':0,'new':0,'unchanged':0,'failed':0,'faces':0,'speed':0.0,'eta_seconds':None,'provider':'','workers':0,'mode':'auto','last_error':'','last_file':'','last_faces':0}
EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
MODEL_VERSION='arcface-buffalo-l-fast-cuda-v5'
FACE_APPS={}; FACE_LOCK=threading.RLock()
cv2.setLogLevel(0)
app=FastAPI(docs_url=None,redoc_url=None)
class ScanRequest(BaseModel): folder:str; mode:str='auto'
class ExportRequest(BaseModel): output_folder:str

def safe_folder_name(name:str):
    return ''.join('_' if char in '<>:"/\\|?*' else char for char in name).strip('. ') or 'Unnamed person'
def copy_to_folder(paths,folder:Path):
    folder.mkdir(parents=True,exist_ok=True); count=0
    for raw in paths:
        src=Path(raw)
        if not src.exists(): continue
        target=folder/src.name
        if target.exists(): target=folder/f'{src.stem}_{hashlib.sha1(str(src).encode()).hexdigest()[:8]}{src.suffix}'
        shutil.copy2(src,target); count+=1
    return count
def providers(): return ort.get_available_providers() if ort else []
def active_model_providers(engine):
    model=FACE_APPS.get(engine)
    if model is None:return []
    found=set()
    for item in getattr(model,'models',{}).values():
        session=getattr(item,'session',None)
        if session is not None:
            try: found.update(session.get_providers())
            except Exception: pass
    return sorted(found)
def normalize_mode(mode):
    value=(mode or 'auto').strip().lower()
    return value if value in {'auto','gpu','cpu','both'} else 'auto'
def provider_for(engine):
    av=set(providers())
    if engine=='gpu':
        # Prefer CUDA on NVIDIA. DirectML remains available for non-CUDA GPUs.
        if 'CUDAExecutionProvider' in av:return ['CUDAExecutionProvider','CPUExecutionProvider']
        if 'DmlExecutionProvider' in av:return ['DmlExecutionProvider','CPUExecutionProvider']
        raise RuntimeError('GPU mode requested, but CUDA/DirectML is unavailable.')
    return ['CPUExecutionProvider']
def prepare_model(engine):
    if FaceAnalysis is None: raise RuntimeError('Face model is not installed. Run pip install -r backend\\requirements.txt.')
    with FACE_LOCK:
        if engine not in FACE_APPS:
            ps=provider_for(engine)
            model=FaceAnalysis(name='buffalo_l',allowed_modules=['detection','recognition'],providers=ps)
            # ctx_id=-1 is CPU in InsightFace; use GPU context when GPU mode is requested.
            ctx_id=0 if engine=='gpu' else -1
            model.prepare(ctx_id=ctx_id,det_size=(320,320))
            # Verify the actual ONNX sessions, not only the requested provider list.
            active=set()
            for item in getattr(model,'models',{}).values():
                session=getattr(item,'session',None)
                if session is not None:
                    try: active.update(session.get_providers())
                    except Exception: pass
            if engine=='gpu' and not ({'DmlExecutionProvider','CUDAExecutionProvider'} & active):
                raise RuntimeError(f"GPU requested but model sessions are using {sorted(active) or ['unknown']}.")
            FACE_APPS[engine]=model
    return FACE_APPS[engine]
def engine_label(engine):
    return 'GPU (CUDA preferred)' if engine=='gpu' else 'CPU'
def mode_plan(mode):
    av=set(providers()); has_gpu=('DmlExecutionProvider' in av or 'CUDAExecutionProvider' in av)
    if mode=='cpu': return ['cpu']
    if mode=='gpu':
        if not has_gpu: raise RuntimeError('GPU mode requested, but no DirectML/CUDA provider is installed.')
        return ['gpu']
    if mode=='both':
        if not has_gpu: raise RuntimeError('CPU + GPU mode requested, but no DirectML/CUDA provider is installed.')
        return ['gpu','cpu']
    return ['gpu'] if has_gpu else ['cpu']
def migrate_model_index():
    with DB_LOCK:
        row=DB.execute('SELECT value FROM settings WHERE key=?',('face_model',)).fetchone()
        if row and row[0]==MODEL_VERSION:return
        DB.execute('DELETE FROM faces');DB.execute('DELETE FROM face_processed');DB.execute('DELETE FROM people')
        DB.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('face_model',MODEL_VERSION));DB.commit()
def descriptors(file,engine):
    try:
        raw=np.fromfile(str(file),dtype=np.uint8); image=cv2.imdecode(raw,cv2.IMREAD_COLOR)
        if image is None:return []
        h,w=image.shape[:2]; largest=max(h,w)
        if largest>1600:
            scale=1600/largest; image=cv2.resize(image,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
        faces=prepare_model(engine).get(image)
        out=[]
        for face in faces:
            emb=np.asarray(face.embedding,dtype=np.float32); emb/=np.linalg.norm(emb)+1e-8; out.append(emb)
        return out
    except Exception as error:
        with LOCK: STATE['last_error']=f"{Path(file).name}: {error}"
        return []
def load_people():
    with DB_LOCK: rows=DB.execute('SELECT id,name,embedding,photos FROM people').fetchall()
    result={}
    for ident,name,raw,photos in rows:
        if raw:
            vec=np.frombuffer(raw,dtype=np.float32).copy(); vec/=np.linalg.norm(vec)+1e-8
            result[int(ident)]={'name':name,'embedding':vec,'photos':int(photos or 0)}
    return result
def match(vector,people):
    if not people:
        with DB_LOCK:
            ident=DB.execute('SELECT COALESCE(MAX(id),0)+1 FROM people').fetchone()[0]
            DB.execute('INSERT INTO people(id,name,embedding,photos) VALUES(?,?,?,0)',(ident,f'Person {ident}',vector.tobytes()))
        people[ident]={'name':f'Person {ident}','embedding':vector.copy(),'photos':0}; return ident
    ids=list(people); matrix=np.stack([people[i]['embedding'] for i in ids]); scores=matrix@vector; idx=int(np.argmax(scores)); score=float(scores[idx])
    if score>=0.58:
        ident=ids[idx]; p=people[ident]; count=p['photos']; updated=(p['embedding']*count+vector)/(count+1); updated/=np.linalg.norm(updated)+1e-8; p['embedding']=updated; p['photos']=count+1; return ident
    with DB_LOCK:
        ident=int(DB.execute('SELECT COALESCE(MAX(id),0) FROM people').fetchone()[0])+1
        DB.execute('INSERT INTO people(id,name,embedding,photos) VALUES(?,?,?,0)',(ident,f'Person {ident}',vector.tobytes()))
    people[ident]={'name':f'Person {ident}','embedding':vector.copy(),'photos':0}; return ident
def persist_people(people):
    with DB_LOCK:
        for ident,p in people.items():
            DB.execute('UPDATE people SET embedding=?,photos=? WHERE id=?',(p['embedding'].astype(np.float32).tobytes(),p['photos'],ident))
        DB.commit()
def scan(folder,mode='auto'):
    mode=normalize_mode(mode)
    try:
        with LOCK: STATE.update(state='scanning',message='Loading face models…',total=0,processed=0,new=0,unchanged=0,failed=0,faces=0,speed=0.0,eta_seconds=None,mode=mode,provider='',workers=0)
        migrate_model_index(); engines=mode_plan(mode)
        for e in engines: prepare_model(e)
        active=[]
        for e in engines: active.extend(active_model_providers(e))
        with LOCK: STATE['provider']=' + '.join(sorted(set(active))) or 'CPUExecutionProvider'
    except Exception as error:
        with LOCK: STATE.update(state='error',message=f'Face model could not start: {error}')
        return
    files=[p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXT]
    with DB_LOCK: existing={r[0]:r[1] for r in DB.execute('SELECT path,modified_ns FROM images').fetchall()}
    people=load_people()
    cpu_workers=max(2,min(4,(os.cpu_count() or 4)//2))
    # CUDA supports concurrent inference calls; use two GPU workers to keep the NVIDIA device fed.
    # CPU inference uses several workers. Both-mode shares one queue so the faster engine gets more work.
    if mode=='cpu': worker_plan=['cpu']*cpu_workers
    elif mode=='gpu': worker_plan=['gpu']*2*2
    elif mode=='both': worker_plan=['gpu']*2+['cpu']*min(2,cpu_workers)
    else: worker_plan=['gpu']*2 if engines==['gpu'] else ['cpu']*cpu_workers
    label=' + '.join(engine_label(e) for e in engines)
    with LOCK:
        detected=STATE.get('provider') or label
        STATE.update(total=len(files),provider=detected,workers=len(worker_plan),message=f'Scanning with {label} ({len(worker_plan)} workers, dynamic queue)…')
    work_queue=queue.Queue()
    for p in files: work_queue.put(p)
    completed=0; start=time.perf_counter()
    def process(e):
        nonlocal completed
        while True:
            try: file=work_queue.get_nowait()
            except queue.Empty: return
            try:
                stat=file.stat(); key=str(file)
                old=existing.get(key)
                if old is not None and old==stat.st_mtime_ns:
                    with LOCK:
                        completed+=1; STATE['processed']=completed; STATE['unchanged']+=1
                    continue
                with LOCK: STATE['last_file']=str(file)
                vectors=descriptors(file,e)
                with LOCK: STATE['last_faces']=len(vectors)
                ids=[]
                with PEOPLE_LOCK:
                    for v in vectors: ids.append(match(v,people))
                with DB_LOCK:
                    DB.execute('DELETE FROM faces WHERE image_path=?',(key,))
                    for ident in ids:
                        DB.execute('INSERT OR REPLACE INTO faces(image_path,person_id) VALUES(?,?)',(key,ident))
                    DB.execute('INSERT OR REPLACE INTO face_processed(image_path) VALUES(?)',(key,))
                    DB.execute('INSERT OR REPLACE INTO images(path,modified_ns,digest,scanned_at) VALUES(?,?,?,?)',(key,stat.st_mtime_ns,'',datetime.now(timezone.utc).isoformat()))
                    if completed%32==0: DB.commit()
                with LOCK:
                    completed+=1; STATE['processed']=completed; STATE['new']+=1; STATE['faces']+=len(vectors)
                    elapsed=max(time.perf_counter()-start,.001); speed=completed/elapsed
                    STATE['speed']=speed; STATE['eta_seconds']=max(len(files)-completed,0)/speed
            except Exception as error:
                with LOCK:
                    completed+=1; STATE['processed']=completed; STATE['failed']+=1
                    STATE['last_error']=f"{Path(file).name}: {error}"
            finally:
                work_queue.task_done()
    threads=[threading.Thread(target=process,args=(engine,),daemon=True) for engine in worker_plan]
    for t in threads:t.start()
    for t in threads:t.join()
    persist_people(people)
    with DB_LOCK: DB.execute('UPDATE people SET photos=(SELECT COUNT(DISTINCT image_path) FROM faces WHERE person_id=people.id)'); DB.execute('DELETE FROM people WHERE photos=0'); DB.commit()
    elapsed=max(time.perf_counter()-start,.001)
    with LOCK: STATE.update(state='complete',message=f'Face scan complete — {completed:,} photos processed.',speed=completed/elapsed,eta_seconds=0)
@app.get('/')
def home(): return FileResponse(ROOT/'web'/'index.html')
@app.get('/api/status')
def status():
    with LOCK:return dict(STATE)
@app.post('/api/scan')
def start(request:ScanRequest):
    folder=Path(request.folder.strip().strip('"')).expanduser()
    if not folder.is_dir():raise HTTPException(400,'That folder does not exist.')
    with LOCK:
        if STATE['state']=='scanning':raise HTTPException(409,'A scan is already running.')
    threading.Thread(target=scan,args=(folder.resolve(),request.mode),daemon=True).start(); return {'ok':True,'mode':normalize_mode(request.mode)}
@app.get('/api/people')
def people():
    with DB_LOCK:
        rows=DB.execute('''
            SELECT p.id,p.name,COUNT(DISTINCT f.image_path) AS photos
            FROM people p LEFT JOIN faces f ON f.person_id=p.id
            GROUP BY p.id,p.name
            ORDER BY photos DESC,p.name
        ''').fetchall()
    return [{'id':x[0],'name':x[1],'photos':x[2]} for x in rows]
def person_images(person_id:int):
    with DB_LOCK:return [r[0] for r in DB.execute('SELECT image_path FROM faces WHERE person_id=? ORDER BY image_path',(person_id,)).fetchall()]
def export_person(person_id:int,output_folder:str):
    if not output_folder.strip():raise ValueError('Choose an output folder.')
    with DB_LOCK:
        row=DB.execute('SELECT name FROM people WHERE id=?',(person_id,)).fetchone(); paths=[r[0] for r in DB.execute('SELECT image_path FROM faces WHERE person_id=?',(person_id,)).fetchall()]
    if not row:raise ValueError('That person group no longer exists.')
    folder=Path(output_folder)/safe_folder_name(row[0]); return {'copied':copy_to_folder(paths,folder),'folder':str(folder)}
def export_all_people(output_folder:str):
    if not output_folder.strip():raise ValueError('Choose an output folder.')
    with DB_LOCK: groups=DB.execute('SELECT id,name FROM people').fetchall()
    total=sum(export_person(i,output_folder)['copied'] for i,_ in groups); return {'copied':total,'groups':len(groups),'folder':str(Path(output_folder))}
def reset_library():
    with LOCK:
        if STATE['state']=='scanning':raise ValueError('Wait for the current scan to finish before resetting.')
    with DB_LOCK:
        for table in ('faces','face_processed','people','images'): DB.execute(f'DELETE FROM {table}')
        DB.commit()
    with LOCK: STATE.update(state='ready',message='Library cleared. Choose a folder to scan.',total=0,processed=0,new=0,unchanged=0,failed=0,faces=0,speed=0.0,eta_seconds=None)
@app.post('/api/people/{person_id}/rename')
def rename(person_id:int,body:dict):
    name=str(body.get('name','')).strip()
    if not name:raise HTTPException(400,'Enter a name.')
    try:
        with DB_LOCK: DB.execute('UPDATE people SET name=? WHERE id=?',(name,person_id)); DB.commit()
    except sqlite3.IntegrityError:raise HTTPException(400,'That name is already used.')
    return {'ok':True}
@app.post('/api/export-unknown')
def export(request:ExportRequest):
    if not request.output_folder.strip():raise HTTPException(400,'Choose an output folder.')
    out=Path(request.output_folder.strip().strip('"')).expanduser()/'Unknown'
    with DB_LOCK: paths=DB.execute('SELECT path FROM images WHERE path NOT IN (SELECT image_path FROM faces)').fetchall()
    return {'copied':copy_to_folder([r[0] for r in paths],out),'folder':str(out)}
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8765)
