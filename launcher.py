"""Enhanced launcher for Face Sorter.
Keeps the original desktop UI as a safe base while providing a recycled,
low-item-count People gallery and non-blocking exports.
"""
from __future__ import annotations
import threading, queue
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk, ImageOps
import desktop
from backend import service

BG=desktop.BG; PANEL=desktop.PANEL; PANEL2=desktop.PANEL2; CARD=desktop.CARD
BORDER=desktop.BORDER; TEXT=desktop.TEXT; MUTED=desktop.MUTED; ACCENT=desktop.ACCENT
ACCENT_H=desktop.ACCENT_H; GREEN=desktop.GREEN; WHITE=desktop.WHITE

# Preserve face memory when manual merge/consolidation removes source people.
_original_merge=service.merge_people
_original_consolidate=service.consolidate_people
_original_reset=service.reset_library

def _merge_with_memory(ids):
    ids=list(dict.fromkeys(int(x) for x in ids))
    with service.DB_LOCK:
        proto={i:[r[0] for r in service.DB.execute('SELECT embedding FROM person_embeddings WHERE person_id=?',(i,)).fetchall()] for i in ids}
    target=_original_merge(ids)
    with service.DB_LOCK:
        for source,embs in proto.items():
            if source==target: continue
            for emb in embs:
                service.DB.execute('INSERT OR IGNORE INTO person_embeddings(person_id,embedding,created_at) VALUES(?,?,?)',
                                    (target,emb,None))
        service.DB.commit()
    return target

def _consolidate_with_memory(threshold=0.62):
    with service.DB_LOCK:
        rows=service.DB.execute('SELECT id FROM people').fetchall()
        samples={}
        proto={}
        for (ident,) in rows:
            sample=service.DB.execute('SELECT image_path FROM faces WHERE person_id=? LIMIT 1',(ident,)).fetchone()
            samples[int(ident)]=sample[0] if sample else None
            proto[int(ident)]=[r[0] for r in service.DB.execute('SELECT embedding FROM person_embeddings WHERE person_id=?',(ident,)).fetchall()]
    merged=_original_consolidate(threshold)
    with service.DB_LOCK:
        for source,sample in samples.items():
            if not sample: continue
            row=service.DB.execute('SELECT person_id FROM faces WHERE image_path=? LIMIT 1',(sample,)).fetchone()
            if not row: continue
            target=int(row[0])
            for emb in proto.get(source,[]):
                service.DB.execute('INSERT OR IGNORE INTO person_embeddings(person_id,embedding,created_at) VALUES(?,?,?)',(target,emb,None))
        service.DB.commit()
    return merged

def _reset_with_memory():
    result=_original_reset()
    with service.DB_LOCK:
        service.DB.execute('DELETE FROM person_embeddings')
        service.DB.commit()
    return result

service.merge_people=_merge_with_memory
service.consolidate_people=_consolidate_with_memory
service.reset_library=_reset_with_memory

class EnhancedFaceSorter(desktop.FaceSorter):
    def __init__(self):
        self.sort_mode=tk.StringVar(value="Most photos")
        self._search_after=None
        self._thumb_queue=queue.Queue()
        self._gallery_slots=[]
        self._gallery_slot_person={}
        self._thumb_cache={}
        super().__init__()
        self.bind_all('<Control-a>',self._select_all_key)
        self.bind_all('<Escape>',self._clear_selection_key)
        self.after(40,self._poll_thumbnails)

    def _gallery_area(self,main):
        head=tk.Frame(main,bg=BG); head.pack(fill='x',padx=30,pady=(2,8))
        tk.Label(head,text='People',bg=BG,fg=TEXT,font=('Segoe UI',16,'bold')).pack(side='left')
        self.people_count=tk.Label(head,text='0 people',bg=BG,fg=MUTED,font=('Segoe UI',9)); self.people_count.pack(side='left',padx=10)
        tools=tk.Frame(head,bg=BG); tools.pack(side='right')
        self.sort_box=ttk.Combobox(tools,textvariable=self.sort_mode,state='readonly',width=16,
                                   values=('Most photos','Name A–Z','Name Z–A','Fewest photos'))
        self.sort_box.pack(side='left',padx=(0,10)); self.sort_box.bind('<<ComboboxSelected>>',lambda e:self.render_gallery())
        searchwrap=tk.Frame(tools,bg=PANEL2,highlightthickness=1,highlightbackground=BORDER)
        searchwrap.pack(side='left')
        tk.Label(searchwrap,text='⌕',bg=PANEL2,fg=MUTED,font=('Segoe UI',14)).pack(side='left',padx=(9,3))
        searchbox=tk.Entry(searchwrap,textvariable=self.search,bg=PANEL2,fg=TEXT,insertbackground=TEXT,
                            relief='flat',bd=0,font=('Segoe UI',9),width=25)
        searchbox.pack(side='left',ipady=8,padx=(0,8))
        self.search.trace_add('write',self._search_changed)
        self.gallery_host=tk.Frame(main,bg=BG); self.gallery_host.pack(fill='both',expand=True,padx=30)
        self.canvas=tk.Canvas(self.gallery_host,bg=BG,highlightthickness=0,bd=0)
        self.scrollbar=ttk.Scrollbar(self.gallery_host,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left',fill='both',expand=True); self.scrollbar.pack(side='right',fill='y')
        self.canvas.bind('<MouseWheel>',self._wheel)
        self.canvas.bind('<Button-1>',self._gallery_click)
        self.canvas.bind('<Double-Button-1>',self._gallery_double_click)
        self.canvas.bind('<Configure>',lambda e:self._schedule_gallery_layout())
        self._gallery_after=None
        self._gallery_generation=0
        self._empty_gallery()

    def _search_changed(self,*_):
        if self._search_after:
            try:self.after_cancel(self._search_after)
            except Exception:pass
        self._search_after=self.after(220,self.render_gallery)

    def _sort_groups(self,groups):
        mode=self.sort_mode.get()
        if mode=='Name A–Z': return sorted(groups,key=lambda g:(g['name'] or '').lower())
        if mode=='Name Z–A': return sorted(groups,key=lambda g:(g['name'] or '').lower(),reverse=True)
        if mode=='Fewest photos': return sorted(groups,key=lambda g:(g['photos'],g['name'].lower()))
        return sorted(groups,key=lambda g:(-g['photos'],g['name'].lower()))

    def render_gallery(self):
        query=self.search.get().strip().lower()
        self.filtered_groups=self._sort_groups([g for g in self.groups if not query or query in g['name'].lower()])
        self.people_count.config(text=f'{len(self.filtered_groups):,} people')
        self.canvas.yview_moveto(0)
        self._gallery_generation+=1
        self._gallery_jobs={}
        self._gallery_slot_person.clear()
        self._build_gallery_pool()

    def _build_gallery_pool(self):
        self.gallery_host.update_idletasks()
        width=max(600,self.canvas.winfo_width()); height=max(320,self.canvas.winfo_height())
        card_w,card_h,gap=170,235,12
        cols=max(3,min(10,int((width-20)//(card_w+gap))))
        rows_total=(len(self.filtered_groups)+cols-1)//cols
        total_h=max(1,rows_total*(card_h+gap)+20)
        self.canvas.configure(scrollregion=(0,0,width,total_h))
        visible_rows=max(2,int(height//(card_h+gap))+3)
        needed=min(120,max(cols*visible_rows,cols*5))
        while len(self._gallery_slots)<needed:
            self._gallery_slots.append(self._new_gallery_slot())
        self._layout_gallery_pool(cols,card_w,card_h,gap)

    def _new_gallery_slot(self):
        tag=('slot',str(len(self._gallery_slots)))
        bg=self.canvas.create_rectangle(0,0,0,0,fill=CARD,outline=BORDER,width=1,state='hidden',tags=tag)
        panel=self.canvas.create_rectangle(0,0,0,0,fill=PANEL2,outline='',state='hidden',tags=tag)
        thumb=self.canvas.create_image(0,0,state='hidden',tags=tag)
        name=self.canvas.create_text(0,0,anchor='w',fill=TEXT,font=('Segoe UI',10,'bold'),state='hidden',tags=tag)
        count=self.canvas.create_text(0,0,anchor='w',fill=MUTED,font=('Segoe UI',8),state='hidden',tags=tag)
        return {'bg':bg,'panel':panel,'thumb':thumb,'name':name,'count':count,'person':None,'photo':None}

    def _layout_gallery_pool(self,cols,card_w=170,card_h=235,gap=12):
        top=self.canvas.canvasy(0); height=max(320,self.canvas.winfo_height())
        first=max(0,int(top//(card_h+gap))-1); rows=max(2,int(height//(card_h+gap))+3)
        start=first*cols; end=min(len(self.filtered_groups),start+rows*cols)
        visible_count=end-start
        for slot_index,slot in enumerate(self._gallery_slots):
            data_index=start+slot_index
            if slot_index>=visible_count:
                self._hide_slot(slot); continue
            g=self.filtered_groups[data_index]; ident=int(g['id']); r,c=divmod(data_index,cols)
            x=8+c*(card_w+gap); y=10+r*(card_h+gap)
            slot['person']=ident; self._gallery_slot_person[slot['bg']]=ident
            self._gallery_slot_person[slot['panel']]=ident; self._gallery_slot_person[slot['thumb']]=ident
            self._gallery_slot_person[slot['name']]=ident; self._gallery_slot_person[slot['count']]=ident
            for item in slot.values():
                if isinstance(item,int): self.canvas.itemconfigure(item,state='normal')
            self.canvas.coords(slot['bg'],x,y,x+card_w,y+card_h)
            self.canvas.coords(slot['panel'],x+6,y+6,x+card_w-6,y+176)
            self.canvas.coords(slot['thumb'],x+card_w/2,y+91)
            self.canvas.coords(slot['name'],x+10,y+190); self.canvas.coords(slot['count'],x+10,y+211)
            self.canvas.itemconfigure(slot['name'],text=g['name']); self.canvas.itemconfigure(slot['count'],text=f"{g['photos']:,} photos")
            self._style_slot(slot,ident)
            photo=self._thumb_cache.get(ident)
            if photo:
                slot['photo']=photo; self.canvas.itemconfigure(slot['thumb'],image=photo,state='normal')
            else:
                slot['photo']=None; self.canvas.itemconfigure(slot['thumb'],image='',state='hidden')
                if ident not in self._gallery_jobs:
                    self._gallery_jobs[ident]=self._gallery_generation
                    threading.Thread(target=self._load_thumb,args=(self._gallery_generation,ident),daemon=True).start()

    def _hide_slot(self,slot):
        slot['person']=None
        for key in ('bg','panel','thumb','name','count'):
            self.canvas.itemconfigure(slot[key],state='hidden')

    def _style_slot(self,slot,ident):
        selected=ident in self.selected_ids
        self.canvas.itemconfigure(slot['bg'],fill='#251b3a' if selected else CARD,outline=ACCENT if selected else BORDER)

    def _load_thumb(self,generation,ident):
        try:
            path=service.person_thumbnail(ident)
            if not path:return
            with Image.open(path) as im:
                im=ImageOps.fit(im.convert('RGB'),(158,158),method=Image.Resampling.LANCZOS)
                self._thumb_queue.put((ident,im.copy()))
        except Exception:
            pass

    def _poll_thumbnails(self):
        try:
            for _ in range(8):
                ident,im=self._thumb_queue.get_nowait()
                photo=ImageTk.PhotoImage(im)
                self._thumb_cache[ident]=photo
                for slot in self._gallery_slots:
                    if slot['person']==ident:
                        slot['photo']=photo; self.canvas.itemconfigure(slot['thumb'],image=photo,state='normal')
                self._gallery_jobs.pop(ident,None)
        except queue.Empty:
            pass
        self.after(50,self._poll_thumbnails)

    def _schedule_gallery_layout(self):
        if self._gallery_after:
            try:self.after_cancel(self._gallery_after)
            except Exception:pass
        self._gallery_after=self.after(100,self._build_gallery_pool)

    def _wheel(self,event):
        self.canvas.yview_scroll(int(-event.delta/120),'units'); self._schedule_gallery_layout()

    def _gallery_person_id(self,event):
        x=self.canvas.canvasx(event.x); y=self.canvas.canvasy(event.y)
        hit=self.canvas.find_overlapping(x,y,x,y)
        for item in reversed(hit):
            ident=self._gallery_slot_person.get(item)
            if ident is not None:return ident
        return None

    def _gallery_click(self,event):
        ident=self._gallery_person_id(event)
        if ident is None:return
        ctrl=bool(event.state & 0x0004)
        if ctrl:
            if ident in self.selected_ids:self.selected_ids.remove(ident)
            else:self.selected_ids.add(ident)
        else:self.selected_ids={ident}
        self.selection_label.config(text=f'{len(self.selected_ids)} selected')
        for slot in self._gallery_slots:
            if slot['person'] is not None:self._style_slot(slot,slot['person'])

    def _gallery_double_click(self,event):
        ident=self._gallery_person_id(event)
        if ident is not None:self.open_person(ident)

    def _select_all_key(self,event=None):
        self.selected_ids={int(g['id']) for g in self.filtered_groups}; self.selection_label.config(text=f'{len(self.selected_ids)} selected')
        for slot in self._gallery_slots:
            if slot['person'] is not None:self._style_slot(slot,slot['person'])
        return 'break'

    def _clear_selection_key(self,event=None):
        self.selected_ids.clear(); self.selection_label.config(text='0 selected')
        for slot in self._gallery_slots:
            if slot['person'] is not None:self._style_slot(slot,slot['person'])
        return 'break'

    def _bottom_bar(self,main):
        bar=tk.Frame(main,bg=BG); bar.pack(fill='x',padx=30,pady=(10,18))
        self.selection_label=tk.Label(bar,text='0 selected',bg=BG,fg=MUTED,font=('Segoe UI',9)); self.selection_label.pack(side='left')
        self.button(bar,'Select all',self._select_all_key).pack(side='left',padx=(14,4))
        self.button(bar,'Clear',self._clear_selection_key).pack(side='left',padx=4)
        self.button(bar,'Rename',self.rename).pack(side='left',padx=4)
        self.button(bar,'Consolidate',self.consolidate_existing).pack(side='left',padx=4)
        self.button(bar,'Merge selected',self.merge_selected).pack(side='left',padx=4)
        self.button(bar,'Check for updates',self.check_updates).pack(side='left',padx=4)
        self.button(bar,'Export selected',self.export_selected).pack(side='right')
        self.button(bar,'Export all people',self.export_all,True).pack(side='right',padx=6)
        self.button(bar,'Export unknown',self.export_unknown).pack(side='right',padx=6)

    def _background_export(self,kind,ids=None):
        folder=filedialog.askdirectory(title='Choose output folder')
        if not folder:return
        self.status.set('Export running in background…')
        def worker():
            try:
                if kind=='selected': result=service.export_person(ids[0],folder)
                elif kind=='all': result=service.export_all_people(folder)
                else: result=service.export(service.ExportRequest(output_folder=folder))
                self.after(0,lambda:messagebox.showinfo('Export complete',f"Copied {result.get('copied',0):,} photo(s)."))
                self.after(0,lambda:self.status.set('Export complete.'))
            except Exception as e:
                self.after(0,lambda e=e:messagebox.showerror('Export failed',str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def export_selected(self):
        if len(self.selected_ids)!=1:return messagebox.showinfo('Export','Select one person.')
        self._background_export('selected',list(self.selected_ids))
    def export_all(self): self._background_export('all')
    def export_unknown(self): self._background_export('unknown')

    def show_settings(self):
        messagebox.showinfo('Face Sorter settings',
            'Performance profile\n\n• People gallery uses recycled canvas slots\n• Thumbnails decode off the UI thread\n• Search is debounced\n• Exports run in the background\n• CPU / GPU / CPU + GPU modes remain available\n\nIdentity memory is kept locally and is used on future scans.')

if __name__=='__main__':
    EnhancedFaceSorter().mainloop()
