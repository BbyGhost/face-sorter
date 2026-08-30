"""Face Sorter — premium local desktop UI."""
from __future__ import annotations
import os, threading, tkinter as tk, updater
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk, UnidentifiedImageError
from backend import service

BG="#0b0d12"; PANEL="#12151d"; PANEL2="#171b24"; BORDER="#252b36"; TEXT="#f5f7fb"; MUTED="#8e98a8"; ACCENT="#8b5cf6"; ACCENT2="#a78bfa"; GREEN="#34d399"; RED="#fb7185"

class FaceSorter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Face Sorter")
        self.geometry("1240x820"); self.minsize(1050,700); self.configure(bg=BG)
        self.folder=tk.StringVar(); self.scan_mode=tk.StringVar(value="Auto (GPU preferred)")
        self.status=tk.StringVar(value="Ready when you are.")
        self.search=tk.StringVar(); self.groups=[]; self.group_signature=[]; self.filtered_groups=[]
        self.photos=[]; self.photo_index=0; self.preview_image=None; self.person_thumb_cache={}; self.last_state=""
        self._build(); self.after(250,self.refresh)

    def _build(self):
        self._styles()
        root=tk.Frame(self,bg=BG); root.pack(fill="both",expand=True)
        self.sidebar=tk.Frame(root,bg="#0e1117",width=220); self.sidebar.pack(side="left",fill="y"); self.sidebar.pack_propagate(False)
        self._sidebar()
        main=tk.Frame(root,bg=BG); main.pack(side="left",fill="both",expand=True)
        self._header(main); self._workspace(main); self._footer(main)

    def _styles(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure("TCombobox",fieldbackground=PANEL2,background=PANEL2,foreground=TEXT,arrowcolor=MUTED,bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER)
        s.map("TCombobox",fieldbackground=[("readonly",PANEL2)],foreground=[("readonly",TEXT)])
        s.configure("TProgressbar",troughcolor=PANEL2,background=ACCENT,darkcolor=ACCENT,lightcolor=ACCENT,bordercolor=PANEL2)

    def button(self,parent,text,command,primary=False,width=None):
        b=tk.Button(parent,text=text,command=command,bg=ACCENT if primary else PANEL2,fg="white",activebackground="#7c3aed" if primary else "#202633",activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),cursor="hand2",padx=14,pady=9)
        if width:b.config(width=width)
        return b

    def _sidebar(self):
        tk.Label(self.sidebar,text="◈",bg="#0e1117",fg=ACCENT2,font=("Segoe UI",28,"bold")).pack(anchor="w",padx=24,pady=(25,0))
        tk.Label(self.sidebar,text="FACE SORTER",bg="#0e1117",fg=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",padx=24)
        tk.Label(self.sidebar,text="PRIVATE • LOCAL • FAST",bg="#0e1117",fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(2,30))
        self._nav_label("▣  Library",True)
        self._nav_label("◉  People")
        self._nav_label("↗  Export")
        tk.Frame(self.sidebar,bg=BORDER,height=1).pack(fill="x",padx=20,pady=22)
        tk.Label(self.sidebar,text="WORKFLOW",bg="#0e1117",fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(0,10))
        tk.Label(self.sidebar,text="1  Choose folder",bg="#0e1117",fg="#cbd2dd",font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=5)
        tk.Label(self.sidebar,text="2  Scan faces",bg="#0e1117",fg="#cbd2dd",font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=5)
        tk.Label(self.sidebar,text="3  Review & merge",bg="#0e1117",fg="#cbd2dd",font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=5)
        tk.Label(self.sidebar,text="4  Export folders",bg="#0e1117",fg="#cbd2dd",font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=5)
        bottom=tk.Frame(self.sidebar,bg="#0e1117"); bottom.pack(side="bottom",fill="x",padx=20,pady=20)
        self.button(bottom,"⚙  Settings",self.show_settings).pack(fill="x")
        tk.Label(bottom,text="v2.2 • On-device AI",bg="#0e1117",fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",pady=(12,0))

    def _nav_label(self,text,active=False):
        tk.Label(self.sidebar,text=text,bg="#211a32" if active else "#0e1117",fg=TEXT if active else MUTED,font=("Segoe UI",10,"bold" if active else "normal"),anchor="w",padx=18,pady=10).pack(fill="x",padx=12,pady=2)

    def _header(self,main):
        head=tk.Frame(main,bg=BG); head.pack(fill="x",padx=30,pady=(25,18))
        left=tk.Frame(head,bg=BG); left.pack(side="left",fill="x",expand=True)
        tk.Label(left,text="Your photo library",bg=BG,fg=TEXT,font=("Segoe UI",25,"bold")).pack(anchor="w")
        tk.Label(left,text="Group faces privately on your PC. Nothing is uploaded.",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(anchor="w",pady=(3,0))
        pill=tk.Label(head,text="●  LOCAL AI",bg="#13251f",fg=GREEN,font=("Segoe UI",9,"bold"),padx=12,pady=7); pill.pack(side="right",anchor="n")

    def _workspace(self,main):
        top=tk.Frame(main,bg=BG); top.pack(fill="x",padx=30)
        card=tk.Frame(top,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); card.pack(fill="x")
        row=tk.Frame(card,bg=PANEL); row.pack(fill="x",padx=18,pady=16)
        tk.Label(row,text="PHOTO FOLDER",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w")
        pathrow=tk.Frame(row,bg=PANEL); pathrow.pack(fill="x",pady=(6,0))
        self.folder_entry=tk.Entry(pathrow,textvariable=self.folder,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",font=("Segoe UI",10))
        self.folder_entry.pack(side="left",fill="x",expand=True,ipady=9,padx=(0,10))
        self.button(pathrow,"Choose folder",self.choose).pack(side="left")
        scanrow=tk.Frame(card,bg=PANEL); scanrow.pack(fill="x",padx=18,pady=(0,16))
        tk.Label(scanrow,text="ENGINE",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left")
        self.mode_box=ttk.Combobox(scanrow,textvariable=self.scan_mode,state="readonly",width=23,values=("Auto (GPU preferred)","GPU only","CPU only","CPU + GPU"))
        self.mode_box.pack(side="left",padx=(10,16))
        self.button(scanrow,"▶  Start scan",self.start,True).pack(side="left")
        self.button(scanrow,"Ⅱ  Pause",self.pause_scan).pack(side="left",padx=6)
        self.button(scanrow,"■  Stop",self.stop_scan).pack(side="left")
        self.engine_label=tk.Label(scanrow,text="GPU preferred • CUDA / DirectML",bg=PANEL,fg=MUTED,font=("Segoe UI",9)); self.engine_label.pack(side="right")
        prog=tk.Frame(card,bg=PANEL); prog.pack(fill="x",padx=18,pady=(0,16))
        self.progress=ttk.Progressbar(prog,mode="determinate",maximum=100); self.progress.pack(fill="x")
        self.status_label=tk.Label(prog,textvariable=self.status,bg=PANEL,fg=MUTED,font=("Segoe UI",9),anchor="w"); self.status_label.pack(fill="x",pady=(7,0))
        stats=tk.Frame(main,bg=BG); stats.pack(fill="x",padx=30,pady=16)
        self.stat_people=self._stat(stats,"PEOPLE","0"); self.stat_photos=self._stat(stats,"MATCHED PHOTOS","0"); self.stat_speed=self._stat(stats,"SPEED","—"); self.stat_state=self._stat(stats,"STATUS","READY")
        body=tk.Frame(main,bg=BG); body.pack(fill="both",expand=True,padx=30)
        people=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); people.pack(side="left",fill="both",expand=True,padx=(0,10))
        ph=tk.Frame(people,bg=PANEL); ph.pack(fill="x",padx=16,pady=14)
        tk.Label(ph,text="People",bg=PANEL,fg=TEXT,font=("Segoe UI",15,"bold")).pack(side="left")
        self.people_count=tk.Label(ph,text="0 groups",bg=PANEL,fg=MUTED,font=("Segoe UI",9)); self.people_count.pack(side="left",padx=10)
        searchbox=tk.Entry(ph,textvariable=self.search,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",font=("Segoe UI",9),width=24)
        searchbox.pack(side="right",ipady=7); searchbox.insert(0,""); self.search.trace_add("write",lambda *_:self.render_people())
        listwrap=tk.Frame(people,bg=PANEL); listwrap.pack(fill="both",expand=True,padx=12,pady=(0,12))
        self.people=tk.Listbox(listwrap,bg=PANEL,fg=TEXT,selectbackground="#352457",selectforeground="white",highlightthickness=0,bd=0,font=("Segoe UI",10),activestyle="none",selectmode="extended")
        scroll=ttk.Scrollbar(listwrap,orient="vertical",command=self.people.yview); self.people.configure(yscrollcommand=scroll.set)
        self.people.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y"); self.people.bind("<<ListboxSelect>>",self.select_person)
        actions=tk.Frame(people,bg=PANEL); actions.pack(fill="x",padx=14,pady=(0,14))
        self.button(actions,"Rename",self.rename).pack(side="left"); self.button(actions,"Merge selected",self.merge_selected).pack(side="left",padx=6); self.button(actions,"Consolidate",self.consolidate_existing).pack(side="left")
        preview=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER,width=400); preview.pack(side="right",fill="both"); preview.pack_propagate(False)
        tk.Label(preview,text="Preview",bg=PANEL,fg=TEXT,font=("Segoe UI",15,"bold")).pack(anchor="w",padx=18,pady=(14,0))
        self.preview=tk.Label(preview,text="Select a person to preview photos",bg="#0e1117",fg=MUTED,font=("Segoe UI",10),anchor="center"); self.preview.pack(fill="both",expand=True,padx=18,pady=12)
        self.photo_text=tk.Label(preview,text="",bg=PANEL,fg=MUTED,font=("Segoe UI",8),anchor="w",justify="left"); self.photo_text.pack(fill="x",padx=18)
        controls=tk.Frame(preview,bg=PANEL); controls.pack(fill="x",padx=18,pady=14)
        self.button(controls,"‹",lambda:self.move_photo(-1),width=3).pack(side="left"); self.button(controls,"›",lambda:self.move_photo(1),width=3).pack(side="left",padx=5); self.button(controls,"Open original",self.open_photo).pack(side="right")

    def _stat(self,parent,label,value):
        card=tk.Frame(parent,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); card.pack(side="left",fill="x",expand=True,padx=4)
        tk.Label(card,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=14,pady=(10,0))
        var=tk.StringVar(value=value); tk.Label(card,textvariable=var,bg=PANEL,fg=TEXT,font=("Segoe UI",16,"bold")).pack(anchor="w",padx=14,pady=(2,10))
        return var

    def _footer(self,main):
        bar=tk.Frame(main,bg=BG); bar.pack(fill="x",padx=30,pady=(12,20))
        self.button(bar,"↻  Reset library",self.reset).pack(side="left")
        self.button(bar,"Check for updates",self.check_updates).pack(side="left",padx=6)
        self.button(bar,"Export no-face photos",self.export).pack(side="right")
        self.button(bar,"Export selected",self.export_selected).pack(side="right",padx=6)
        self.button(bar,"Export all people",self.export_all,True).pack(side="right")

    def show_settings(self):
        messagebox.showinfo("Settings","Face Sorter runs fully locally.\\n\\nGPU: CUDA preferred, DirectML supported.\\nMatching and export thresholds are kept conservative to reduce accidental merges.")

    def choose(self):
        folder=filedialog.askdirectory(title="Choose your photo folder")
        if folder:self.folder.set(folder)

    def start(self):
        path=Path(self.folder.get().strip())
        if not path.is_dir():return messagebox.showerror("Face Sorter","Choose a valid photo folder.")
        if service.STATE["state"]=="scanning":return
        mode_map={"Auto (GPU preferred)":"auto","GPU only":"gpu","CPU only":"cpu","CPU + GPU":"both"}
        mode=mode_map[self.mode_box.get()]
        if mode in {"gpu","both"}:
            available=service.providers()
            if "DmlExecutionProvider" not in available and "CUDAExecutionProvider" not in available:
                return messagebox.showerror("GPU unavailable",f"No CUDA/DirectML provider was found.\\n\\nDetected: {', '.join(available) or 'None'}")
        threading.Thread(target=service.scan,args=(path,mode),daemon=True).start()

    def pause_scan(self):
        try:service.pause_scan()
        except Exception as e:messagebox.showwarning("Scan",str(e))
    def resume_scan(self):
        try:service.resume_scan()
        except Exception as e:messagebox.showwarning("Scan",str(e))
    def stop_scan(self):
        if messagebox.askyesno("Stop scan","Stop the current scan? Completed results will be kept."):
            try:service.cancel_scan()
            except Exception as e:messagebox.showwarning("Scan",str(e))

    def refresh(self):
        state=service.status(); total=state["total"]; processed=state["processed"]; speed=state.get("speed") or 0
        self.progress["value"]=(processed/total*100) if total else 0
        people=len(service.people())
        self.stat_people.set(f"{people:,}"); self.stat_photos.set(f"{state.get('faces',0):,}"); self.stat_speed.set(f"{speed:.1f}/s" if speed else "—"); self.stat_state.set(state["state"].upper())
        eta=state.get("eta_seconds"); extra=f"{processed:,} / {total:,}" if total else ""
        if speed:extra+=f"  •  {speed:.1f} photos/s"
        if eta is not None and state["state"]=="scanning":extra+=f"  •  ETA {int(eta//60)}m"
        self.status.set(state["message"]+(f"   {extra}" if extra else ""))
        if state.get("provider"):self.engine_label.config(text=f"{state['provider']}  •  {state.get('workers',0)} worker(s)")
        if state.get("state")=="scanning" and state.get("last_file"):self._show_path(state["last_file"],"Scanning")
        groups=service.people(); signature=[(g["id"],g["name"],g["photos"]) for g in groups]
        if signature!=self.group_signature:
            current=self.groups[self.people.curselection()[0]]["id"] if self.people.curselection() and self.people.curselection()[0]<len(self.groups) else None
            self.groups=groups; self.group_signature=signature; self.render_people(current)
        self.after(900,self.refresh)

    def render_people(self,current=None):
        query=self.search.get().strip().lower(); self.filtered_groups=[g for g in self.groups if not query or query in g["name"].lower()]
        self.people.delete(0,tk.END)
        for g in self.filtered_groups:
            self.people.insert(tk.END,f"  {g['name']}                                      {g['photos']:,}")
        self.people_count.config(text=f"{len(self.filtered_groups):,} groups")
        if current:
            for i,g in enumerate(self.filtered_groups):
                if g["id"]==current:self.people.selection_set(i); self.people.see(i); break

    def select_person(self,_=None):
        selected=self.people.curselection()
        if not selected:return
        self.photos=service.person_images(self.filtered_groups[selected[0]]["id"]); self.photo_index=0; self.show_photo()

    def _show_path(self,path,prefix):
        try:
            image=Image.open(path); image.thumbnail((430,430)); self.preview_image=ImageTk.PhotoImage(image); self.preview.config(image=self.preview_image,text="")
            self.photo_text.config(text=f"{prefix}  •  {Path(path).name}")
        except (OSError,UnidentifiedImageError):pass

    def show_photo(self):
        if not self.photos:return
        path=self.photos[self.photo_index]; self._show_path(path,"Photo")
        self.photo_text.config(text=f"Photo {self.photo_index+1} of {len(self.photos)}  •  {Path(path).name}")

    def move_photo(self,amount):
        if self.photos:self.photo_index=(self.photo_index+amount)%len(self.photos); self.show_photo()
    def open_photo(self):
        if self.photos:os.startfile(self.photos[self.photo_index])

    def rename(self):
        selected=self.people.curselection()
        if not selected:return messagebox.showinfo("Face Sorter","Select a person first.")
        g=self.filtered_groups[selected[0]]; name=simpledialog.askstring("Rename person","Person name:",initialvalue=g["name"])
        if name:
            try:service.rename(g["id"],{"name":name}); self.group_signature=[]
            except Exception as e:messagebox.showerror("Rename",str(e))

    def merge_selected(self):
        selected=self.people.curselection()
        if len(selected)<2:return messagebox.showinfo("Merge people","Ctrl-click or Shift-click two or more groups.")
        ids=[self.filtered_groups[i]["id"] for i in selected]
        if not messagebox.askyesno("Merge people",f"Merge {len(ids)} selected groups into one person?"):return
        try:service.merge_people(ids); self.group_signature=[]
        except ValueError as e:messagebox.showerror("Merge",str(e))

    def consolidate_existing(self):
        if service.STATE["state"]=="scanning":return messagebox.showinfo("Consolidate","Wait for the scan to finish.")
        if not messagebox.askyesno("Consolidate people","Find likely duplicate groups and combine them?"):return
        try:
            n=service.consolidate_existing(); self.group_signature=[]; messagebox.showinfo("Consolidated",f"Combined {n} duplicate group(s).")
        except ValueError as e:messagebox.showerror("Consolidate",str(e))

    def export(self):
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder:
            r=service.export(service.ExportRequest(output_folder=folder)); messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s).\\n\\n{r['folder']}")

    def export_selected(self):
        selected=self.people.curselection()
        if not selected:return messagebox.showinfo("Export","Select a person first.")
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder:
            try:
                r=service.export_person(self.filtered_groups[selected[0]]["id"],folder); messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s).\\n\\n{r['folder']}")
            except ValueError as e:messagebox.showerror("Export",str(e))

    def export_all(self):
        folder=filedialog.askdirectory(title="Choose output folder")
        if folder and messagebox.askyesno("Export all people","Create one folder per consolidated person?\\n\\nOriginal photos will not be changed."):
            try:
                r=service.export_all_people(folder); messagebox.showinfo("Export complete",f"Copied {r['copied']:,} photo(s) into {r['groups']:,} person folder(s).")
            except Exception as e:messagebox.showerror("Export",str(e))

    def check_updates(self):
        def worker():
            try:
                result=updater.check()
                if not result.get("update"):self.after(0,lambda:messagebox.showinfo("Updates",f"You are up to date (v{result.get('current')})."));return
                def ask():
                    if messagebox.askyesno("Update available",f"Version {result['remote']} is available.\\n\\nOnly changed files will be downloaded. Install now?"):
                        try:updater.apply(result); self.destroy(); updater.restart()
                        except Exception as e:messagebox.showerror("Update failed",str(e))
                self.after(0,ask)
            except Exception as e:self.after(0,lambda:messagebox.showwarning("Updater",str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def reset(self):
        if messagebox.askyesno("Reset library","Remove the local index and person groups? Original photos will NOT be deleted."):
            try:service.reset_library()
            except ValueError as e:messagebox.showwarning("Reset",str(e))

if __name__=="__main__":FaceSorter().mainloop()
