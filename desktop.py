"""Face Sorter desktop application — no browser or localhost required."""
from __future__ import annotations
import os
import threading
import tkinter as tk
import updater
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk, UnidentifiedImageError
from backend import service

class FaceSorter(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Face Sorter"); self.geometry("1000x760"); self.minsize(800,600); self.configure(bg="#111319")
        self.folder=tk.StringVar(); self.scan_mode=tk.StringVar(value="auto"); self.status=tk.StringVar(value="Choose a photo folder to begin."); self.groups=[]; self.group_signature=[]; self.photos=[]; self.photo_index=0; self.preview_image=None
        self._build(); self.after(300,self.refresh)
    def _build(self):
        style=ttk.Style(self); style.theme_use("clam"); style.configure("TFrame",background="#111319"); style.configure("TLabel",background="#111319",foreground="#f3f1f8")
        style.configure("Title.TLabel",font=("Segoe UI",27,"bold")); style.configure("Sub.TLabel",foreground="#adb2bf"); style.configure("TButton",font=("Segoe UI",10,"bold"),padding=9); style.configure("TProgressbar",troughcolor="#2b303a",background="#a783ff")
        outer=ttk.Frame(self,padding=28); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="Face Sorter",style="Title.TLabel").pack(anchor="w"); ttk.Label(outer,text="Private face grouping that runs entirely on this computer.",style="Sub.TLabel").pack(anchor="w",pady=(2,20))
        ttk.Label(outer,text="Photo folder").pack(anchor="w"); top=ttk.Frame(outer); top.pack(fill="x",pady=(7,10)); ttk.Entry(top,textvariable=self.folder).pack(side="left",fill="x",expand=True,padx=(0,8)); ttk.Button(top,text="Choose folder",command=self.choose).pack(side="left")
        scanbar=ttk.Frame(outer); scanbar.pack(fill="x",pady=(0,8))
        ttk.Label(scanbar,text="Scan engine").pack(side="left")
        self.mode_box=ttk.Combobox(scanbar,textvariable=self.scan_mode,state="readonly",width=22,values=("Auto (GPU preferred)","GPU only","CPU only","CPU + GPU"))
        self.mode_box.current(0); self.mode_box.pack(side="left",padx=(10,0))
        self.mode_box.bind("<<ComboboxSelected>>", self.on_mode_change)
        self.selected_mode_label=tk.StringVar(value="Selected: Auto (GPU preferred)")
        ttk.Label(scanbar,textvariable=self.selected_mode_label,style="Sub.TLabel").pack(side="left",padx=(12,0))
        ttk.Label(scanbar,text="GPU mode requires DirectML/CUDA.",style="Sub.TLabel").pack(side="left",padx=(12,0))
        scan_controls=ttk.Frame(outer); scan_controls.pack(anchor="w")
ttk.Button(scan_controls,text="Start face scan",command=self.start).pack(side="left")
ttk.Button(scan_controls,text="Pause",command=self.pause_scan).pack(side="left",padx=(8,0))
ttk.Button(scan_controls,text="Resume",command=self.resume_scan).pack(side="left",padx=(8,0))
ttk.Button(scan_controls,text="Stop",command=self.stop_scan).pack(side="left",padx=(8,0))
self.progress=ttk.Progressbar(outer,mode="determinate",maximum=100); self.progress.pack(fill="x",pady=(15,6)); ttk.Label(outer,textvariable=self.status,style="Sub.TLabel").pack(anchor="w")
        ttk.Separator(outer).pack(fill="x",pady=18); content=ttk.Frame(outer); content.pack(fill="both",expand=True)
        left=ttk.Frame(content); left.pack(side="left",fill="both",expand=True,padx=(0,18)); ttk.Label(left,text="People found",font=("Segoe UI",15,"bold")).pack(anchor="w"); ttk.Label(left,text="Select a group to see its photos.",style="Sub.TLabel").pack(anchor="w",pady=(3,8))
        people_box=ttk.Frame(left); people_box.pack(fill="both",expand=True)
        self.people=tk.Listbox(people_box,height=12,bg="#1c1f27",fg="#f3f1f8",selectbackground="#7458b5",borderwidth=0,font=("Segoe UI",11),selectmode="extended")
        people_scroll=ttk.Scrollbar(people_box,orient="vertical",command=self.people.yview)
        self.people.configure(yscrollcommand=people_scroll.set); self.people.pack(side="left",fill="both",expand=True); people_scroll.pack(side="right",fill="y")
        self.people.bind("<<ListboxSelect>>",self.select_person); people_actions=ttk.Frame(left); people_actions.pack(fill="x",pady=(10,0)); ttk.Button(people_actions,text="Rename selected",command=self.rename).pack(side="left"); ttk.Button(people_actions,text="Merge selected",command=self.merge_selected).pack(side="left",padx=(8,0))
        right=ttk.Frame(content,width=400); right.pack(side="right",fill="both"); right.pack_propagate(False); ttk.Label(right,text="Photo preview",font=("Segoe UI",15,"bold")).pack(anchor="w"); self.preview=tk.Label(right,text="Select a person to view photos",bg="#1c1f27",fg="#adb2bf",width=45,height=18,anchor="center"); self.preview.pack(fill="both",expand=True,pady=(10,8)); self.photo_text=tk.StringVar(value=""); ttk.Label(right,textvariable=self.photo_text,style="Sub.TLabel",wraplength=370).pack(anchor="w")
        controls=ttk.Frame(right); controls.pack(fill="x",pady=(8,0)); ttk.Button(controls,text="◀ Previous",command=lambda:self.move_photo(-1)).pack(side="left"); ttk.Button(controls,text="Next ▶",command=lambda:self.move_photo(1)).pack(side="left",padx=7); ttk.Button(controls,text="Open photo",command=self.open_photo).pack(side="right")
        bottom=ttk.Frame(outer); bottom.pack(fill="x",pady=(16,0)); ttk.Button(bottom,text="Reset library",command=self.reset).pack(side="left"); ttk.Button(bottom,text="Check for updates",command=self.check_updates).pack(side="left",padx=(8,0)); ttk.Button(bottom,text="Sort into person folders",command=self.export_all).pack(side="right"); ttk.Button(bottom,text="Export selected person",command=self.export_selected).pack(side="right",padx=(0,8)); ttk.Button(bottom,text="Export photos without faces",command=self.export).pack(side="right",padx=(0,8))
    def pause_scan(self):
        try: service.pause_scan()
        except Exception as error: messagebox.showwarning("Face Sorter",str(error))
    def resume_scan(self):
        try: service.resume_scan()
        except Exception as error: messagebox.showwarning("Face Sorter",str(error))
    def stop_scan(self):
        if messagebox.askyesno("Stop scan","Stop the current scan? Completed results will be kept."):
            try: service.cancel_scan()
            except Exception as error: messagebox.showwarning("Face Sorter",str(error))
    def merge_selected(self):
        selected=self.people.curselection()
        if len(selected)<2:return messagebox.showinfo("Merge people","Select two or more people using Ctrl-click or Shift-click.")
        ids=[self.groups[i]['id'] for i in selected]
        if not messagebox.askyesno("Merge people",f"Merge {len(ids)} selected groups into one person?\n\nTheir photos will be combined."):return
        try:
            service.merge_people(ids); self.group_signature=[]; self.people.selection_clear(0,tk.END)
        except ValueError as error: messagebox.showerror("Merge people",str(error))
    def choose(self):
        folder=filedialog.askdirectory(title="Choose your photo folder")
        if folder:self.folder.set(folder)
    def on_mode_change(self,_event=None):
        selected=self.mode_box.get()
        self.scan_mode.set(selected)
        self.selected_mode_label.set(f"Selected: {selected}")

    def start(self):
        path=Path(self.folder.get().strip())
        if not path.is_dir():return messagebox.showerror("Face Sorter","Choose a valid photo folder.")
        if service.STATE['state']=='scanning':return
        mode_map={'Auto (GPU preferred)':'auto','GPU only':'gpu','CPU only':'cpu','CPU + GPU':'both'}
        selected=self.mode_box.get()
        mode=mode_map.get(selected)
        if mode is None:
            return messagebox.showerror("Face Sorter","Please select a valid scan engine.")
        if mode in {"gpu","both"}:
            available=service.providers()
            if "DmlExecutionProvider" not in available and "CUDAExecutionProvider" not in available:
                return messagebox.showerror("GPU unavailable",f"{selected} requires a GPU execution provider.\n\nDetected providers:\n{', '.join(available) or 'None'}\n\nInstall onnxruntime-directml in this virtual environment, then restart Face Sorter.")
        self.scan_mode.set(selected)
        self.selected_mode_label.set(f"Selected: {selected}")
        threading.Thread(target=service.scan,args=(path,mode),daemon=True).start()
    def refresh(self):
        state=service.status(); total=state['total']; self.progress['value']=(state['processed']/total*100) if total else 0; speed=state.get('speed') or 0
        eta=state.get('eta_seconds'); extra=f"  {state['processed']:,} / {total:,}"
        if speed: extra+=f"  •  {speed:.1f} photos/s"
        if eta is not None and state.get('state')=='scanning':
            mins=int(eta//60); extra+=f"  •  ETA {mins}m" if mins else f"  •  ETA {int(eta)}s"
        self.status.set(state['message']+extra if total else state['message'])
        if state.get('provider'):
            self.selected_mode_label.set(f"Running: {state['provider']} • Mode: {state.get('mode','auto').upper()}")
        if state.get('state')=='scanning' and state.get('last_file'):
            try:
                image=Image.open(state['last_file']); image.thumbnail((390,390))
                self.preview_image=ImageTk.PhotoImage(image)
                self.preview.configure(image=self.preview_image,text="")
                self.photo_text.set(f"Scanning: {state['last_file']}")
            except (OSError,UnidentifiedImageError):
                pass
        selected=self.people.curselection(); current=self.groups[selected[0]]['id'] if selected and selected[0]<len(self.groups) else None; groups=service.people()
        signature=[(group['id'],group['name'],group['photos']) for group in groups]
        if signature!=self.group_signature:
            scroll_at=self.people.yview()[0]; self.groups=groups; self.group_signature=signature; self.people.delete(0,tk.END)
            for group in self.groups:self.people.insert(tk.END,f"{group['name']} — {group['photos']} photo(s)")
            self.people.yview_moveto(scroll_at)
            if current:
                for index,group in enumerate(self.groups):
                    if group['id']==current:self.people.selection_set(index);break
        self.after(1200,self.refresh)
    def select_person(self,_event=None):
        selected=self.people.curselection()
        if not selected:return
        self.photos=service.person_images(self.groups[selected[0]]['id']); self.photo_index=0; self.show_photo()
    def show_photo(self):
        if not self.photos:return
        path=self.photos[self.photo_index]
        try:
            image=Image.open(path); image.thumbnail((390,390)); self.preview_image=ImageTk.PhotoImage(image); self.preview.configure(image=self.preview_image,text="")
            self.photo_text.set(f"Photo {self.photo_index+1} of {len(self.photos)}\n{path}")
        except (OSError,UnidentifiedImageError):
            self.preview.configure(image="",text="This image cannot be previewed."); self.photo_text.set(path)
    def move_photo(self,amount):
        if self.photos:self.photo_index=(self.photo_index+amount)%len(self.photos); self.show_photo()
    def open_photo(self):
        if self.photos:os.startfile(self.photos[self.photo_index])
    def rename(self):
        selected=self.people.curselection()
        if not selected:return messagebox.showinfo("Face Sorter","Select a person first.")
        person=self.groups[selected[0]]; name=simpledialog.askstring("Rename person","Name:",initialvalue=person['name'])
        if name:
            try:service.rename(person['id'],{'name':name})
            except Exception as error:messagebox.showerror("Face Sorter",str(error))
    def export(self):
        folder=filedialog.askdirectory(title="Choose an output folder")
        if folder:
            result=service.export(service.ExportRequest(output_folder=folder));messagebox.showinfo("Face Sorter",f"Copied {result['copied']} photo(s) to:\n{result['folder']}")
    def export_selected(self):
        selected=self.people.curselection()
        if not selected:return messagebox.showinfo("Face Sorter","Select a person group first.")
        folder=filedialog.askdirectory(title="Choose an output folder")
        if folder:
            try:
                result=service.export_person(self.groups[selected[0]]['id'],folder);messagebox.showinfo("Face Sorter",f"Copied {result['copied']} photo(s) to:\n{result['folder']}")
            except ValueError as error:messagebox.showerror("Face Sorter",str(error))
    def export_all(self):
        folder=filedialog.askdirectory(title="Choose an output folder")
        if folder:
            if not messagebox.askyesno("Sort photos", "Create one folder per detected person and copy the matching photos there?\n\nYour original photos will not be changed."):return
            result=service.export_all_people(folder);messagebox.showinfo("Face Sorter",f"Sorted {result['copied']} photo(s) into {result['groups']} combined person folder(s) from {result.get('original_groups', result['groups'])} detected groups:\n{result['folder']}")
    def check_updates(self):
        def worker():
            try:
                result=updater.check()
                if not result.get("update"):
                    self.after(0,lambda:messagebox.showinfo("Face Sorter",f"You are up to date (v{result.get('current')}).")); return
                changed=result.get("changed",[])
                def ask():
                    if messagebox.askyesno("Update available",f"Version {result['remote']} is available.\n\nOnly {len(changed)} changed file(s) will be downloaded.\n\nInstall update now?"):
                        try:
                            updater.apply(result)
                            messagebox.showinfo("Updated","Update installed successfully. Face Sorter will restart.")
                            self.destroy(); updater.restart()
                        except Exception as error: messagebox.showerror("Update failed",str(error))
                self.after(0,ask)
            except Exception as error:
                self.after(0,lambda:messagebox.showwarning("Updater",str(error)))
        threading.Thread(target=worker,daemon=True).start()
    def reset(self):
        if not messagebox.askyesno("Reset library","Remove the local scan index and all person groups? Your original photos will not be deleted."):return
        try:service.reset_library()
        except ValueError as error:messagebox.showwarning("Face Sorter",str(error))
if __name__=='__main__':FaceSorter().mainloop()
