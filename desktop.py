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
        self.canvas.bind("<MouseWheel>",self._wheel)
        self.canvas.bind("<Button-1>",self._gallery_click)
        self.canvas.bind("<Double-Button-1>",self._gallery_double_click)
        self.canvas.bind("<Configure>",lambda e:self._schedule_gallery_render())
        self.canvas.bind("<Key>",lambda e:None)
        self.canvas.bind("<ButtonRelease-1>",lambda e:self._schedule_gallery_render())
        self._gallery_after=None
        self._gallery_jobs={}
        self._gallery_images={}
        self._gallery_generation=0
        self._empty_gallery()

    def _wheel(self,event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-event.delta/120),"units")
            self._schedule_gallery_render()

    def _empty_gallery(self):
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0,0,max(self.canvas.winfo_width(),900),400))
        w=max(self.canvas.winfo_width(),900)
        self.canvas.create_text(w//2,120,text="Your people will appear here",fill=TEXT,
                                font=("Segoe UI",15,"bold"),tags=("empty",))
        self.canvas.create_text(w//2,155,text="Choose a photo folder and start a scan to build your visual library.",
                                fill=MUTED,font=("Segoe UI",10),tags=("empty",))

    def _schedule_gallery_render(self):
        if self._gallery_after:
            try:self.after_cancel(self._gallery_after)
            except Exception:pass
        self._gallery_after=self.after(80,self._render_visible_gallery)

    def render_gallery(self):
        query=self.search.get().strip().lower()
        self.filtered_groups=[g for g in self.groups if not query or query in g["name"].lower()]
        self._gallery_generation+=1
        generation=self._gallery_generation
        self._gallery_jobs={}
        self._gallery_images={}
        self.canvas.delete("all")
        self.people_count.config(text=f"{len(self.filtered_groups):,} people")
        if not self.filtered_groups:
            self._empty_gallery(); return
        self.after_idle(self._render_visible_gallery)

    def _render_visible_gallery(self):
        if not self.filtered_groups:return
        generation=self._gallery_generation
        width=max(self.canvas.winfo_width(),900)
        card_w=170; card_h=235; gap=12
        cols=max(3,min(7,int(width//(card_w+gap))))
        rows=(len(self.filtered_groups)+cols-1)//cols
        total_h=max(1,rows*(card_h+gap)+20)
        self.canvas.configure(scrollregion=(0,0,width,total_h))
        first=max(0,int(self.canvas.canvasy(0)//(card_h+gap))-1)
        last=min(len(self.filtered_groups),int((self.canvas.canvasy(self.canvas.winfo_height())+self.canvas.canvasy(0))//(card_h+gap))+2)
        self.canvas.delete("card")
        for idx in range(first,last):
            g=self.filtered_groups[idx]; r,c=divmod(idx,cols)
            x=8+c*(card_w+gap); y=10+r*(card_h+gap)
            ident=g["id"]; selected=ident in self.selected_ids
            bg="#251b3a" if selected else CARD
            self.canvas.create_rectangle(x,y,x+card_w,y+card_h,fill=bg,outline=ACCENT if selected else BORDER,width=1,tags=("card",f"person:{ident}"))
            self.canvas.create_rectangle(x+6,y+6,x+card_w-6,y+176,fill=PANEL2,outline="",tags=("card",f"person:{ident}"))
            self.canvas.create_text(x+card_w/2,y+91,text="◉",fill=MUTED,font=("Segoe UI",30),tags=("card",f"person:{ident}"))
            self.canvas.create_text(x+10,y+190,text=g["name"],anchor="w",fill=TEXT,font=("Segoe UI",10,"bold"),
                                    tags=("card",f"person:{ident}"))
            self.canvas.create_text(x+10,y+211,text=f"{g['photos']:,} photos",anchor="w",fill=MUTED,font=("Segoe UI",8),
                                    tags=("card",f"person:{ident}"))
            if ident not in self._gallery_images and ident not in self._gallery_jobs:
                self._gallery_jobs[ident]=generation
                threading.Thread(target=self._load_one_gallery_thumbnail,args=(generation,ident),daemon=True).start()

    def _load_one_gallery_thumbnail(self,generation,ident):
        try:
            path=service.person_thumbnail(ident)
            if not path:return
            with Image.open(path) as im:
                im=ImageOps.fit(im.convert("RGB"),(158,158),method=Image.Resampling.LANCZOS)
                data=im.copy()
            self.after(0,self._install_gallery_thumbnail,generation,ident,data)
        except Exception:
            self.after(0,self._finish_gallery_job,generation,ident)

    def _finish_gallery_job(self,generation,ident):
        if generation==self._gallery_generation:self._gallery_jobs.pop(ident,None)

    def _install_gallery_thumbnail(self,generation,ident,im):
        if generation!=self._gallery_generation:return
        try:
            photo=ImageTk.PhotoImage(im)
            self._gallery_images[ident]=photo
            self._gallery_jobs.pop(ident,None)
            self._render_visible_gallery()
        except Exception:
            self._finish_gallery_job(generation,ident)

    def _gallery_person_id(self,event):
        item=self.canvas.find_withtag("current")
        if not item:return None
        tags=self.canvas.gettags(item[0])
        for t in tags:
            if t.startswith("person:"):
                try:return int(t.split(":",1)[1])
                except ValueError:return None
        return None

    def _gallery_click(self,event):
        ident=self._gallery_person_id(event)
        if ident is None:return
        ctrl=bool(event.state & 0x0004)
        if ctrl:
            if ident in self.selected_ids:self.selected_ids.remove(ident)
            else:self.selected_ids.add(ident)
        else:
            self.selected_ids={ident}
        self.selection_label.config(text=f"{len(self.selected_ids)} selected")
        self._render_visible_gallery()
        if not ctrl:
            self.open_person(ident)

    def _gallery_double_click(self,event):
        ident=self._gallery_person_id(event)
        if ident is not None:self.open_person(ident)

    def _person_card(self,*args,**kwargs):
        # Kept for compatibility with older callers.
        return None

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
