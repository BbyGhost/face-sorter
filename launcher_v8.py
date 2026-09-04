"""Face Sorter v3.3.6 - premium organized UI and library tools."""
from __future__ import annotations
import os, threading, tkinter as tk, updater
from tkinter import filedialog, messagebox, simpledialog, ttk
from launcher_v7 import EnhancedFaceSorter as _EnhancedFaceSorter
from backend import service

BG="#080a0f"; SIDEBAR="#0c0f15"; PANEL="#11151d"; PANEL2="#171c26"; CARD="#151a23"
BORDER="#252c38"; TEXT="#f7f8fb"; MUTED="#8d96a6"; ACCENT="#8b5cf6"; ACCENT_H="#7c3aed"
GREEN="#34d399"; RED="#fb7185"; WHITE="#ffffff"

class EnhancedFaceSorter(_EnhancedFaceSorter):
    def __init__(self):
        self._settings_win=None
        super().__init__()
        # v7 added a duplicate button to the bottom bar. Keep duplicates in the
        # Tools/Settings areas instead so the main action bar stays clean.
        try:
            bar=self.selection_label.master
            for child in list(bar.winfo_children()):
                try:
                    if child.cget("text")=="Find duplicates": child.destroy()
                except Exception: pass
        except Exception: pass

    def _sidebar(self):
        tk.Label(self.sidebar,text="◈",bg=SIDEBAR,fg="#a78bfa",font=("Segoe UI",30,"bold")).pack(anchor="w",padx=24,pady=(22,0))
        tk.Label(self.sidebar,text="FACE SORTER",bg=SIDEBAR,fg=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",padx=24)
        tk.Label(self.sidebar,text="PRIVATE  ·  ON-DEVICE AI",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(2,26))
        self.nav_people=tk.Label(self.sidebar,text="  ◉   People",bg="#211a32",fg=TEXT,font=("Segoe UI",10,"bold"),anchor="w",padx=14,pady=11,cursor="hand2")
        self.nav_people.pack(fill="x",padx=12,pady=3)
        self.nav_library=tk.Label(self.sidebar,text="  ▦   All photos",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",10),anchor="w",padx=14,pady=11,cursor="hand2")
        self.nav_library.pack(fill="x",padx=12,pady=3)
        self.nav_library.bind("<Button-1>",lambda e:self._show_library_hint())
        tk.Frame(self.sidebar,bg=BORDER,height=1).pack(fill="x",padx=20,pady=18)
        tk.Label(self.sidebar,text="LIBRARY TOOLS",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=24,pady=(0,7))
        for text,cmd in (("  ◌   Find duplicates",self.find_duplicates),("  ◇   Library health",self.library_health),("  ↻   Rebuild index",self.rebuild_index)):
            self.button(self.sidebar,text,cmd).pack(fill="x",padx=12,pady=3)
        bottom=tk.Frame(self.sidebar,bg=SIDEBAR); bottom.pack(side="bottom",fill="x",padx=20,pady=18)
        self.button(bottom,"⚙  Settings",self.show_settings).pack(fill="x")
        tk.Label(bottom,text="v3.3.6  ·  Local AI",bg=SIDEBAR,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",pady=(10,0))

    def _topbar(self,main):
        bar=tk.Frame(main,bg=BG); bar.pack(fill="x",padx=30,pady=(22,12))
        left=tk.Frame(bar,bg=BG); left.pack(side="left",fill="x",expand=True)
        tk.Label(left,text="Your people",bg=BG,fg=TEXT,font=("Segoe UI",27,"bold")).pack(anchor="w")
        tk.Label(left,text="Organize faces, review memories and keep your photo library clean.",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(anchor="w",pady=(2,0))
        tk.Label(bar,text="●  PRIVATE & LOCAL",bg="#10231d",fg=GREEN,font=("Segoe UI",9,"bold"),padx=13,pady=7).pack(side="right",anchor="n")

    def rename(self):
        if len(self.selected_ids)!=1:
            messagebox.showinfo("Rename person","Select exactly one person first.",parent=self); return
        ident=int(next(iter(self.selected_ids)))
        row=service.DB.execute("SELECT name FROM people WHERE id=?",(ident,)).fetchone()
        if not row:return
        name=simpledialog.askstring("Rename person","Person name:",initialvalue=row[0],parent=self)
        if name is None:return
        name=name.strip()
        if not name or name==row[0]:return
        try:
            with service.DB_LOCK:
                service.DB.execute("UPDATE people SET name=? WHERE id=?",(name,ident)); service.DB.commit()
            self.refresh()
        except Exception as e:messagebox.showerror("Rename failed",str(e),parent=self)

    def _gallery_double_click(self,event):
        ident=self._gallery_person_id(event)
        if ident is None:return
        x=self.canvas.canvasx(event.x); y=self.canvas.canvasy(event.y)
        items=self.canvas.find_overlapping(x,y,x,y)
        gallery=getattr(self,"_gallery_items",{}).get(ident,{})
        if gallery.get("name") in items:
            self.selected_ids={ident}; self._update_selection_visuals(); self.rename(); return
        self.open_person(ident)

    def show_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():self._settings_win.lift();return
        win=tk.Toplevel(self); self._settings_win=win; win.title("Face Sorter Settings"); win.geometry("720x660"); win.minsize(650,560); win.configure(bg=BG); win.transient(self)
        head=tk.Frame(win,bg=BG); head.pack(fill="x",padx=30,pady=(25,16))
        tk.Label(head,text="Settings",bg=BG,fg=TEXT,font=("Segoe UI",25,"bold")).pack(anchor="w")
        tk.Label(head,text="Manage your local index, cleanup, performance and updates.",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(anchor="w",pady=(3,0))
        body=tk.Frame(win,bg=BG); body.pack(fill="both",expand=True,padx=30)
        self._settings_group(body,"LIBRARY",[
            ("Clear library index","Forget people, face assignments, prototypes and scan history. Original photos are never touched.",self.clear_library,"Clear"),
            ("Find duplicate photos","Find exact duplicate files, review the KEEP / REMOVE list, then delete only the copies you approve.",self.find_duplicates,"Review"),
            ("Library health","Check for missing originals and stale index entries without deleting any photos.",self.library_health,"Check"),
            ("Rebuild index","Mark the library for a full re-check while preserving saved people and face memory.",self.rebuild_index,"Rebuild"),
        ])
        self._settings_group(body,"APPLICATION",[
            ("Check for updates","Check GitHub from inside the app, download the required changed files and restart automatically.",self.check_for_updates,"Check"),
        ])
        foot=tk.Frame(win,bg=BG); foot.pack(fill="x",padx=30,pady=20)
        tk.Label(foot,text="Face Sorter 3.3.6  ·  Local AI  ·  Photos stay on your PC",bg=BG,fg=MUTED,font=("Segoe UI",8)).pack(side="left")
        self.button(foot,"Close",win.destroy).pack(side="right")

    def _settings_group(self,parent,title,items):
        tk.Label(parent,text=title,bg=BG,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",pady=(8,7))
        for name,desc,cmd,action in items:
            row=tk.Frame(parent,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); row.pack(fill="x",pady=4)
            text=tk.Frame(row,bg=PANEL); text.pack(side="left",fill="x",expand=True,padx=15,pady=11)
            tk.Label(text,text=name,bg=PANEL,fg=TEXT,font=("Segoe UI",10,"bold")).pack(anchor="w")
            tk.Label(text,text=desc,bg=PANEL,fg=MUTED,font=("Segoe UI",8),wraplength=470,justify="left").pack(anchor="w",pady=(3,0))
            self.button(row,action,cmd).pack(side="right",padx=12)

    def check_for_updates(self):
        self.status.set("Checking for updates…")
        def worker():
            try:
                result=updater.check(); remote=result.get("remote",updater.APP_VERSION); current=result.get("current",updater.APP_VERSION)
                if remote==current or not result.get("update"):
                    self.after(0,lambda:self.status.set(f"Up to date · v{current}"))
                    self.after(0,lambda:messagebox.showinfo("Updates",f"You're up to date.\n\nFace Sorter {current}",parent=self)); return
                def ask():
                    if not messagebox.askyesno("Update available",f"Face Sorter {remote} is available.\n\nDownload {len(result.get('changed',[]))} changed file(s) and restart?",parent=self):
                        self.status.set("Update postponed."); return
                    self.status.set("Downloading update…")
                    try:
                        updater.apply(result); self.status.set("Restarting…"); updater.restart(); self.after(250,self.destroy)
                    except Exception as e:self.status.set("Update failed.");messagebox.showerror("Update failed",str(e),parent=self)
                self.after(0,ask)
            except Exception as e:self.after(0,lambda e=e:(self.status.set("Update check failed."),messagebox.showerror("Update check failed",str(e),parent=self)))
        threading.Thread(target=worker,daemon=True).start()

    def clear_library(self):
        if service.STATE.get("state")=="scanning":
            messagebox.showwarning("Scan running","Stop the scan before clearing the library index.",parent=self);return
        ok=messagebox.askyesno("Clear library index","This removes all Face Sorter people, face assignments, prototypes and scan history.\n\nYOUR ORIGINAL PHOTOS WILL NOT BE DELETED.\n\nContinue?",icon="warning",parent=self)
        if not ok:return
        try:
            with service.DB_LOCK:
                for table in ("faces","face_processed","images","person_embeddings","people"):service.DB.execute(f"DELETE FROM {table}")
                service.DB.commit()
            self.selected_ids.clear();self.groups=[];self.filtered_groups=[];self.status.set("Library index cleared — original photos are safe.");self.refresh()
            messagebox.showinfo("Library cleared","The Face Sorter index is empty. Your original photos were not touched.",parent=self)
        except Exception as e:messagebox.showerror("Clear library failed",str(e),parent=self)

    def rebuild_index(self):
        if service.STATE.get("state")=="scanning":
            messagebox.showwarning("Scan running","Stop the scan before rebuilding the index.",parent=self);return
        try:
            with service.DB_LOCK:
                service.DB.execute("DELETE FROM face_processed");service.DB.execute("UPDATE images SET modified_ns=0");service.DB.commit()
            self.status.set("Index marked for rebuild. Run Scan library to re-check your photos.");messagebox.showinfo("Index ready","The next scan will re-check every indexed photo. Saved people and face memory are preserved.",parent=self)
        except Exception as e:messagebox.showerror("Rebuild index failed",str(e),parent=self)

    def library_health(self):
        win=tk.Toplevel(self);win.title("Library health");win.geometry("760x520");win.minsize(650,450);win.configure(bg=BG);win.transient(self)
        tk.Label(win,text="Library health",bg=BG,fg=TEXT,font=("Segoe UI",22,"bold")).pack(anchor="w",padx=26,pady=(22,4))
        status=tk.Label(win,text="Checking indexed files…",bg=BG,fg=MUTED,font=("Segoe UI",9));status.pack(anchor="w",padx=26,pady=(0,12))
        text=tk.Text(win,bg=PANEL,fg=TEXT,relief="flat",bd=0,font=("Consolas",9),wrap="word");text.pack(fill="both",expand=True,padx=26,pady=6)
        self.button(win,"Close",win.destroy).pack(anchor="e",padx=26,pady=18)
        def worker():
            try:
                with service.DB_LOCK:paths=[r[0] for r in service.DB.execute("SELECT path FROM images").fetchall()];assigned=service.DB.execute("SELECT COUNT(*) FROM faces").fetchone()[0];people=service.DB.execute("SELECT COUNT(*) FROM people").fetchone()[0]
                missing=[p for p in paths if not os.path.exists(p)];
                def done():
                    status.config(text="Health check complete")
                    text.insert("end",f"INDEXED PHOTOS       {len(paths):,}\nPEOPLE               {people:,}\nFACE ASSIGNMENTS     {assigned:,}\nMISSING ORIGINALS    {len(missing):,}\n\n")
                    if missing:
                        text.insert("end","Missing originals:\n\n"+"\n".join(missing[:250]))
                        if len(missing)>250:text.insert("end",f"\n\n… and {len(missing)-250:,} more")
                    else:text.insert("end","Everything indexed by Face Sorter currently exists on disk.\n")
                    text.config(state="disabled")
                self.after(0,done)
            except Exception as e:self.after(0,lambda e=e:messagebox.showerror("Health check failed",str(e),parent=win))
        threading.Thread(target=worker,daemon=True).start()

    def _show_library_hint(self):
        messagebox.showinfo("All photos","The People view is optimized for your face-organized library. Use Library health and Find duplicates from the sidebar, and open any person to review their assigned originals.",parent=self)

if __name__=='__main__': EnhancedFaceSorter().mainloop()
