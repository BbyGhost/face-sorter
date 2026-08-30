"""Face Sorter — premium Google Photos inspired desktop UI."""
from __future__ import annotations
import os, threading, tkinter as tk, updater, queue
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from backend import service

BG="#0a0b0f"; SIDEBAR="#0d0f14"; PANEL="#12151c"; PANEL2="#181c25"; CARD="#151922"
BORDER="#252b36"; TEXT="#f7f8fb"; MUTED="#8d96a6"; ACCENT="#8b5cf6"; ACCENT_H="#7c3aed"
GREEN="#34d399"; RED="#fb7185"; WHITE="#ffffff"

class FaceSorter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Face Sorter")
        self.geometry("1440x900"); self.minsize(1120,720); self.configure(bg=BG)
        self.folder=tk.StringVar(); self.scan_mode=tk.StringVar(value="Auto (GPU preferred)")
        self.status=tk.StringVar(value="Ready to organize your library.")
        self.search=tk.StringVar()
        self.groups=[]; self.group_signature=[]; self.filtered_groups=[]
        self.photos=[]; self.photo_index=0; self.preview_image=None
        self.thumb_cache={}; self.card_widgets={}; self.selected_ids=set()
        self.last_folder=""
        self._gallery_generation=0
        self._gallery_queue=queue.Queue()
        self._consolidating=False
        self._merging=False
        self._build(); self.after(300,self.refresh)

    def _styles(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure("TCombobox",fieldbackground=PANEL2,background=PANEL2,foreground=TEXT,arrowcolor=MUTED,
                    bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=8)
        s.map("TCombobox",fieldbackground=[("readonly",PANEL2)],foreground=[("readonly",TEXT)])
        s.configure("TProgressbar",troughcolor=PANEL2,background=ACCENT,darkcolor=ACCENT,lightcolor=ACCENT,bordercolor=PANEL2)

    def button(self,parent,text,command,primary=False,width=None):
        b=tk.Button(parent,text=text,command=command,bg=ACCENT if primary else PANEL2,fg=WHITE,
                    activebackground=ACCENT_H if primary else "#202633",activeforeground=WHITE,
                    relief="flat",bd=0,font=("Segoe UI",10,"bold"),cursor="hand2",padx=14,pady=9)
        if width:b.config(width=width)
        return b

    def _build(self):
        self._styles()
        root=tk.Frame(self,bg=BG); root.pack(fill="both",expand=True)
        self.sidebar=tk.Frame(root,bg=SIDEBAR,width=238); self.sidebar.pack(side="left",fill="y"); self.sidebar.pack_propagate(False)
        self._sidebar()
        main=tk.Frame(root,bg=BG); main.pack(side="left",fill="both",expand=True)
        self._topbar(main); self._scan_card(main); self._stats(main)
        self._gallery_area(main); self._bottom_bar(main)

    def _sidebar(self):
        tk.Label(self.sidebar,text="◈",bg=SIDEBAR,fg="#a78bfa",font=("Segoe UI",30,"bold")).pack(anchor="w",padx=24,pady=(24,0))
        tk.Label(self.sidebar,text="FACE SORTER",bg=SIDEBAR,fg=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",padx=24)
        tk.Label(self.sidebar,text="PRIVATE • ON-DEVICE AI",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(2,28))
        self.nav_people=tk.Label(self.sidebar,text="  ◉   People",bg="#211a32",fg=TEXT,font=("Segoe UI",10,"bold"),anchor="w",padx=14,pady=11)
        self.nav_people.pack(fill="x",padx=12,pady=3)
        self.nav_library=tk.Label(self.sidebar,text="  ▦   All photos",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",10),anchor="w",padx=14,pady=11)
        self.nav_library.pack(fill="x",padx=12,pady=3)
        tk.Frame(self.sidebar,bg=BORDER,height=1).pack(fill="x",padx=20,pady=20)
        tk.Label(self.sidebar,text="WORKFLOW",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(0,8))
        for text in ("01  Choose folder","02  Scan faces","03  Review people","04  Export"):
            tk.Label(self.sidebar,text=text,bg=SIDEBAR,fg="#c4cbd6",font=("Segoe UI",9)).pack(anchor="w",padx=24,pady=5)
        bottom=tk.Frame(self.sidebar,bg=SIDEBAR); bottom.pack(side="bottom",fill="x",padx=20,pady=20)
        self.button(bottom,"⚙  Settings",self.show_settings).pack(fill="x")
        tk.Label(bottom,text="v3.0 • Local AI",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",pady=(11,0))

    def _topbar(self,main):
        bar=tk.Frame(main,bg=BG); bar.pack(fill="x",padx=30,pady=(24,14))
        left=tk.Frame(bar,bg=BG); left.pack(side="left",fill="x",expand=True)
        tk.Label(left,text="People",bg=BG,fg=TEXT,font=("Segoe UI",26,"bold")).pack(anchor="w")
        tk.Label(left,text="A private visual library of the people in your photos.",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(anchor="w",pady=(2,0))
        pill=tk.Label(bar,text="●  LOCAL & PRIVATE",bg="#12251f",fg=GREEN,font=("Segoe UI",9,"bold"),padx=12,pady=7)
        pill.pack(side="right",anchor="n")

    def _scan_card(self,main):
        card=tk.Frame(main,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); card.pack(fill="x",padx=30)
        row=tk.Frame(card,bg=PANEL); row.pack(fill="x",padx=18,pady=14)
        tk.Label(row,text="PHOTO LIBRARY",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w")
        pathrow=tk.Frame(row,bg=PANEL); pathrow.pack(fill="x",pady=(6,0))
        self.folder_entry=tk.Entry(pathrow,textvariable=self.folder,bg=PANEL2,fg=TEXT,insertbackground=TEXT,
                                    relief="flat",font=("Segoe UI",10),highlightthickness=1,highlightbackground=BORDER)
        self.folder_entry.pack(side="left",fill="x",expand=True,ipady=9,padx=(0,10))
        self.button(pathrow,"Choose folder",self.choose).pack(side="left")
        controls=tk.Frame(card,bg=PANEL); controls.pack(fill="x",padx=18,pady=(0,14))
        tk.Label(controls,text="ENGINE",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left")
        self.mode_box=ttk.Combobox(controls,textvariable=self.scan_mode,state="readonly",width=22,
                                   values=("Auto (GPU preferred)","GPU only","CPU only","CPU + GPU"))
        self.mode_box.pack(side="left",padx=(10,14))
        self.button(controls,"▶  Scan library",self.start,True).pack(side="left")
        self.button(controls,"Ⅱ  Pause / Resume",self.toggle_pause).pack(side="left",padx=6)
        self.button(controls,"■  Stop",self.stop_scan).pack(side="left")
        self.engine_label=tk.Label(controls,text="Checking engine…",bg=PANEL,fg=MUTED,font=("Segoe UI",9))
        self.engine_label.pack(side="right")
        prog=tk.Frame(card,bg=PANEL); prog.pack(fill="x",padx=18,pady=(0,14))
        self.progress=ttk.Progressbar(prog,mode="determinate",maximum=100); self.progress.pack(fill="x")
        tk.Label(prog,textvariable=self.status,bg=PANEL,fg=MUTED,font=("Segoe UI",9),anchor="w").pack(fill="x",pady=(7,0))

    def _stats(self,main):
        row=tk.Frame(main,bg=BG); row.pack(fill="x",padx=26,pady=14)
        self.stat_people=self._stat(row,"PEOPLE","0")
        self.stat_photos=self._stat(row,"FACES FOUND","0")
        self.stat_speed=self._stat(row,"SCAN SPEED","—")
        self.stat_state=self._stat(row,"STATUS","READY")

    def _stat(self,parent,label,value):
        card=tk.Frame(parent,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); card.pack(side="left",fill="x",expand=True,padx=4)
        tk.Label(card,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=15,pady=(10,0))
        var=tk.StringVar(value=value); tk.Label(card,textvariable=var,bg=PANEL,fg=TEXT,font=("Segoe UI",17,"bold")).pack(anchor="w",padx=15,pady=(2,10))
        return var

    def _gallery_area(self,main):
        head=tk.Frame(main,bg=BG); head.pack(fill="x",padx=30,pady=(2,8))
        tk.Label(head,text="People",bg=BG,fg=TEXT,font=("Segoe UI",16,"bold")).pack(side="left")
        self.people_count=tk.Label(head,text="0 people",bg=BG,fg=MUTED,font=("Segoe UI",9)); self.people_count.pack(side="left",padx=10)
        searchwrap=tk.Frame(head,bg=PANEL2,highlightthickness=1,highlightbackground=BORDER); searchwrap.pack(side="right")
        tk.Label(searchwrap,text="⌕",bg=PANEL2,fg=MUTED,font=("Segoe UI",14)).pack(side="left",padx=(9,3))
        searchbox=tk.Entry(searchwrap,textvariable=self.search,bg=PANEL2,fg=TEXT,insertbackground=TEXT,
                            relief="flat",bd=0,font=("Segoe UI",9),width=28)
        searchbox.pack(side="left",ipady=8,padx=(0,8))
        self.search.trace_add("write",lambda *_:self.render_gallery())
        self.gallery_host=tk.Frame(main,bg=BG); self.gallery_host.pack(fill="both",expand=True,padx=30)
        self.canvas=tk.Canvas(self.gallery_host,bg=BG,highlightthickness=0,bd=0)
        self.scrollbar=ttk.Scrollbar(self.gallery_host,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left",fill="both",expand=True); self.scrollbar.pack(side="right",fill="y")
        self.gallery=tk.Frame(self.canvas,bg=BG)
        self.gallery_window=self.canvas.create_window((0,0),window=self.gallery,anchor="nw")
        self.gallery.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",self._resize_gallery)
        self.canvas.bind_all("<MouseWheel>",self._wheel)
        self._empty_gallery()

    def _resize_gallery(self,event):
        self.canvas.itemconfigure(self.gallery_window,width=event.width)

    def _wheel(self,event):
        if self.canvas.winfo_exists(): self.canvas.yview_scroll(int(-event.delta/120),"units")

    def _empty_gallery(self):
        for w in self.gallery.winfo_children():w.destroy()
        box=tk.Frame(self.gallery,bg=PANEL,highlightthickness=1,highlightbackground=BORDER)
        box.pack(fill="x",padx=2,pady=2)
        tk.Label(box,text="Your people will appear here",bg=PANEL,fg=TEXT,font=("Segoe UI",15,"bold")).pack(pady=(55,5))
        tk.Label(box,text="Choose a photo folder and start a scan to build your visual library.",bg=PANEL,fg=MUTED,font=("Segoe UI",10)).pack(pady=(0,55))

    def _thumbnail(self,path,size=190):
        key=(path,size)
        if key in self.thumb_cache:return self.thumb_cache[key]
        try:
            with Image.open(path) as im:
                im=ImageOps.fit(im.convert("RGB"),(size,size),method=Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(im)
            self.thumb_cache[key]=photo; return photo
        except (OSError,UnidentifiedImageError): return None

    def render_gallery(self):
        query=self.search.get().strip().lower()
        self.filtered_groups=[g for g in self.groups if not query or query in g["name"].lower()]
        self._gallery_generation+=1
        generation=self._gallery_generation
        for w in self.gallery.winfo_children(): w.destroy()
        self.card_widgets={}
        self.people_count.config(text=f"{len(self.filtered_groups):,} people")
        if not self.filtered_groups:
            self._empty_gallery(); return
        width=max(self.canvas.winfo_width(),900); cols=max(3,min(6,width//220))
        jobs=[]
        for idx,g in enumerate(self.filtered_groups):
            r,c=divmod(idx,cols)
            jobs.append((g,r,c))
            self._person_card(g,r,c)
        threading.Thread(target=self._load_gallery_thumbnails,args=(generation,jobs),daemon=True).start()

    def _load_gallery_thumbnails(self,generation,jobs):
        from PIL import Image
        for index,(g,r,c) in enumerate(jobs):
            if generation!=self._gallery_generation: return
            try:
                path=service.person_thumbnail(g["id"])
                if not path: continue
                with Image.open(path) as im:
                    im=ImageOps.fit(im.convert("RGB"),(190,190),method=Image.Resampling.LANCZOS)
                    self._gallery_queue.put((generation,g["id"],im.copy()))
                # Start painting as soon as the first thumbnails are ready instead
                # of waiting for every person in a large library.
                if index % 4 == 0:
                    self.after(0,self._drain_gallery_queue)
            except Exception: continue
        self.after(0,self._drain_gallery_queue)

    def _drain_gallery_queue(self):
        processed=0
        while processed<6:
            try: generation,ident,im=self._gallery_queue.get_nowait()
            except queue.Empty: break
            if generation!=self._gallery_generation: continue
            card=self.card_widgets.get(ident)
            if not card or not card.winfo_exists(): continue
            photo=ImageTk.PhotoImage(im)
            label=getattr(card,"_image_label",None)
            if label and label.winfo_exists():
                label.configure(image=photo,text="")
                label.image=photo
            processed+=1
        if not self._gallery_queue.empty():
            self.after(20,self._drain_gallery_queue)

    def _person_card(self,g,row,col):
        selected=g["id"] in self.selected_ids
        card=tk.Frame(self.gallery,bg="#251b3a" if selected else CARD,highlightthickness=1,
                      highlightbackground=ACCENT if selected else BORDER,cursor="hand2")
        card.grid(row=row,column=col,sticky="nsew",padx=6,pady=6)
        self.card_widgets[g["id"]]=card
        thumb=None
        if thumb:
            image_label=tk.Label(card,image=thumb,bg=CARD); image_label.image=thumb
        else:
            image_label=tk.Label(card,text="◉",bg=CARD,fg=MUTED,font=("Segoe UI",32))
        image_label.pack(fill="x",padx=5,pady=5)
        info=tk.Frame(card,bg="#251b3a" if selected else CARD); info.pack(fill="x",padx=5,pady=(0,5))
        tk.Label(info,text=g["name"],bg=info["bg"],fg=TEXT,font=("Segoe UI",10,"bold"),anchor="w").pack(fill="x",padx=7,pady=(6,0))
        tk.Label(info,text=f"{g['photos']:,} photos",bg=info["bg"],fg=MUTED,font=("Segoe UI",8),anchor="w").pack(fill="x",padx=7,pady=(1,7))
        for widget in (card,image_label,info):
            widget.bind("<Button-1>",lambda e,ident=g["id"]:self.card_click(ident,e))
            widget.bind("<Double-Button-1>",lambda e,ident=g["id"]:self.open_person(ident))

    def card_click(self,ident,event=None):
        ctrl=bool(event and (event.state & 0x0004))
        if ctrl:
            if ident in self.selected_ids:self.selected_ids.remove(ident)
            else:self.selected_ids.add(ident)
        else:
            self.selected_ids={ident}
            g=next((x for x in self.filtered_groups if x["id"]==ident),None)
            if g:self.show_person(g)
        self.render_gallery()

    def open_person(self,ident):
        g=next((x for x in self.groups if x["id"]==ident),None)
        if g:self.show_person(g)

    def show_person(self,g):
        win=tk.Toplevel(self); win.title(f"{g['name']} • Face Sorter"); win.geometry("1100x760"); win.configure(bg=BG)
        tk.Label(win,text=g["name"],bg=BG,fg=TEXT,font=("Segoe UI",22,"bold")).pack(anchor="w",padx=24,pady=(20,0))
        subtitle=tk.Label(win,text="Loading photos in background…",bg=BG,fg=MUTED,font=("Segoe UI",9)); subtitle.pack(anchor="w",padx=24,pady=(2,12))
        host=tk.Frame(win,bg=BG); host.pack(fill="both",expand=True,padx=20,pady=8)
        canvas=tk.Canvas(host,bg=BG,highlightthickness=0); sb=ttk.Scrollbar(host,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set); canvas.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        grid=tk.Frame(canvas,bg=BG); canvas.create_window((0,0),window=grid,anchor="nw")
        grid.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        self.button(win,"Close",win.destroy).pack(pady=(0,18))
        self._person_gallery_queue=queue.Queue()
        self._person_gallery_generation=getattr(self,"_person_gallery_generation",0)+1
        generation=self._person_gallery_generation
        threading.Thread(target=self._load_person_gallery,args=(g,win,grid,subtitle,canvas,generation),daemon=True).start()

    def _load_person_gallery(self,g,win,grid,subtitle,canvas,generation):
        try:
            photos=service.person_images(g["id"])
        except Exception as e:
            self.after(0,lambda e=e: subtitle.config(text=f"Could not load photos: {e}"))
            return
        if not win.winfo_exists(): return
        self.photos=photos
        self.photo_index=0
        self.after(0,lambda: subtitle.config(text=f"{len(photos):,} photos • loading previews…"))
        for index,path in enumerate(photos):
            if not win.winfo_exists() or generation!=self._person_gallery_generation: return
            try:
                with Image.open(path) as im:
                    im=ImageOps.fit(im.convert("RGB"),(180,180),method=Image.Resampling.LANCZOS)
                    self._person_gallery_queue.put((generation,path,im.copy(),index))
                if index % 4 == 0:
                    self.after(0,self._drain_person_gallery,win,grid,canvas)
            except (OSError,UnidentifiedImageError):
                continue
        self.after(0,self._drain_person_gallery,win,grid,canvas)

    def _drain_person_gallery(self,win,grid,canvas):
        if not win.winfo_exists(): return
        made=0
        while made<8:
            try: generation,path,im,index=self._person_gallery_queue.get_nowait()
            except queue.Empty: break
            if generation!=self._person_gallery_generation: continue
            photo=ImageTk.PhotoImage(im)
            lab=tk.Label(grid,image=photo,bg=CARD,cursor="hand2")
            lab.image=photo
            lab.grid(row=index//5,column=index%5,padx=5,pady=5)
            lab.bind("<Double-Button-1>",lambda e,p=path:os.startfile(p))
            made+=1
        grid.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        if not self._person_gallery_queue.empty():
            self.after(20,self._drain_person_gallery,win,grid,canvas)

    def _bottom_bar(self,main):
        bar=tk.Frame(main,bg=BG); bar.pack(fill="x",padx=30,pady=(10,18))
        self.selection_label=tk.Label(bar,text="0 selected",bg=BG,fg=MUTED,font=("Segoe UI",9)); self.selection_label.pack(side="left")
        self.button(bar,"Reset library",self.reset).pack(side="left",padx=(16,0))
        self.button(bar,"Consolidate people",self.consolidate_existing).pack(side="left",padx=6)
        self.merge_btn=self.button(bar,"Merge selected",self.merge_selected); self.merge_btn.pack(side="left")
        self.button(bar,"Check for updates",self.check_updates).pack(side="left",padx=6)
        self.button(bar,"Export selected",self.export_selected).pack(side="right")
        self.button(bar,"Export all people",self.export_all,True).pack(side="right",padx=6)
        self.button(bar,"Export unknown",self.export_unknown).pack(side="right",padx=6)

    def show_settings(self):
        messagebox.showinfo("Settings","Face Sorter runs locally.\\n\\nGPU modes use CUDA/DirectML when available.\\nFace grouping uses conservative similarity matching and a consolidation pass.\\nOriginal photos are never modified by scanning or export.")

    def choose(self):
        folder=filedialog.askdirectory(title="Choose your photo library")
        if folder:self.folder.set(folder)

    def start(self):
        path=Path(self.folder.get().strip().strip('"'))
        if not path.is_dir():return messagebox.showerror("Choose a folder","Please select a valid photo folder.")
        if service.STATE["state"]=="scanning":return messagebox.showinfo("Scan running","A scan is already running.")
        mode={"Auto (GPU preferred)":"auto","GPU only":"gpu","CPU only":"cpu","CPU + GPU":"both"}[self.mode_box.get()]
        if mode in {"gpu","both"}:
            available=service.providers()
            if "DmlExecutionProvider" not in available and "CUDAExecutionProvider" not in available:
                return messagebox.showerror("GPU unavailable",f"No CUDA/DirectML provider was found.\\n\\nDetected: {', '.join(available) or 'None'}")
        threading.Thread(target=service.scan,args=(path,mode),daemon=True).start()

    def toggle_pause(self):
        try:
            if service.STATE.get("pause_requested"): service.resume_scan()
            else: service.pause_scan()
        except Exception as e:messagebox.showwarning("Scan",str(e))
    def stop_scan(self):
        if messagebox.askyesno("Stop scan","Stop the current scan? Completed results will be kept."):
            try:service.cancel_scan()
            except Exception as e:messagebox.showwarning("Scan",str(e))

    def refresh(self):
        try:
            state=service.status(); total=state.get("total",0); processed=state.get("processed",0); speed=state.get("speed") or 0
            self.progress["value"]=(processed/total*100) if total else 0
            groups=service.people(); self.groups=groups
            self.stat_people.set(f"{len(groups):,}"); self.stat_photos.set(f"{state.get('faces',0):,}")
            self.stat_speed.set(f"{speed:.1f}/s" if speed else "—"); self.stat_state.set(state.get("state","ready").upper())
            extra=f"{processed:,} / {total:,}" if total else ""
            if speed:extra+=f"  •  {speed:.1f} photos/s"
            eta=state.get("eta_seconds")
            if eta is not None and state.get("state")=="scanning":extra+=f"  •  ETA {int(eta//60)}m"
            self.status.set(state.get("message","Ready.")+(f"   {extra}" if extra else ""))
            if state.get("provider"):self.engine_label.config(text=f"{state['provider']}  •  {state.get('workers',0)} worker(s)")
            signature=[(g["id"],g["name"],g["photos"]) for g in groups]
            if signature!=self.group_signature:
                self.group_signature=signature
                self.render_gallery()
            self.selection_label.config(text=f"{len(self.selected_ids)} selected")
        except Exception as e:
            self.status.set(f"UI refresh error: {e}")
        self.after(900,self.refresh)

    def rename(self):
        if len(self.selected_ids)!=1:return messagebox.showinfo("Rename","Select one person first.")
        ident=next(iter(self.selected_ids)); g=next((x for x in self.groups if x["id"]==ident),None)
        if not g:return
        name=simpledialog.askstring("Rename person","Person name:",initialvalue=g["name"])
        if name:
            try:service.rename(ident,{"name":name}); self.group_signature=[]
            except Exception as e:messagebox.showerror("Rename",str(e))

    def merge_selected(self):
        if len(self.selected_ids)<2:
            return messagebox.showinfo("Merge people","Ctrl-click two or more people, then choose Merge selected.")
        if self._merging or self._consolidating:
            return messagebox.showinfo("Busy","Another people operation is already running.")
        ids=list(self.selected_ids)
        if not messagebox.askyesno("Merge people",f"Merge {len(ids)} selected groups into one person?\n\nTheir photos will be combined."): return
        self._merging=True
        self.status.set("Merging selected people in the background…")
        def worker():
            try:
                target=service.merge_people(ids)
                def done():
                    self._merging=False
                    self.selected_ids.clear()
                    self.group_signature=[]
                    self.render_gallery()
                    self.status.set("People merged successfully.")
                self.after(0,done)
            except Exception as e:
                self._merging=False
                self.after(0,lambda:messagebox.showerror("Merge failed",str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def consolidate_existing(self):
        if service.STATE["state"]=="scanning": return messagebox.showinfo("Consolidate","Wait for the scan to finish.")
        if self._consolidating or self._merging: return messagebox.showinfo("Busy","Another people operation is already running.")
        if not messagebox.askyesno("Consolidate people","Find and combine likely duplicate groups?\n\nThis runs in the background. You can continue using the app."): return
        self._consolidating=True
        self.status.set("Consolidating people in the background…")
        def worker():
            try:
                n=service.consolidate_existing()
                def done():
                    self._consolidating=False
                    self.selected_ids.clear()
                    self.group_signature=[]
                    self.render_gallery()
                    self.status.set(f"Consolidation complete — {n} group(s) merged.")
                self.after(0,done)
            except Exception as e:
                self._consolidating=False
                self.after(0,lambda:messagebox.showerror("Consolidation failed",str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def export_selected(self):
        if len(self.selected_ids)!=1:return messagebox.showinfo("Export","Select one person.")
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder:
            try:
                r=service.export_person(next(iter(self.selected_ids)),folder)
                messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s).\\n\\n{r['folder']}")
            except Exception as e:messagebox.showerror("Export",str(e))

    def export_all(self):
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder and messagebox.askyesno("Export all people","Create one folder per consolidated person?\\n\\nOriginal photos will not be changed."):
            try:
                r=service.export_all_people(folder); messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s) into {r['groups']:,} person folder(s).")
            except Exception as e:messagebox.showerror("Export",str(e))

    def export_unknown(self):
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder:
            try:
                r=service.export(service.ExportRequest(output_folder=folder)); messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s) to:\\n{r['folder']}")
            except Exception as e:messagebox.showerror("Export",str(e))

    def check_updates(self):
        def worker():
            try:
                result=updater.check()
                if not result.get("update"):
                    self.after(0,lambda:messagebox.showinfo("Updates",f"You are up to date (v{result.get('current')}).")); return
                def ask():
                    if messagebox.askyesno("Update available",f"Version {result['remote']} is available.\\n\\nOnly changed files will be downloaded. Install now?"):
                        try:updater.apply(result); self.destroy(); updater.restart()
                        except Exception as e:messagebox.showerror("Update failed",str(e))
                self.after(0,ask)
            except Exception as e:self.after(0,lambda:messagebox.showwarning("Updater",str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def reset(self):
        if messagebox.askyesno("Reset library","Remove the local index and person groups? Original photos will NOT be deleted."):
            try:
                service.reset_library(); self.selected_ids.clear(); self.group_signature=[]
            except ValueError as e:messagebox.showwarning("Reset",str(e))

if __name__=="__main__":
    FaceSorter().mainloop()
