"""Face Sorter v3.3.5 - duplicate photo manager.
Adds exact byte-for-byte duplicate detection with a review window and safe
one-copy-per-group removal. Existing person/face data is preserved for kept files.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from launcher_v6 import EnhancedFaceSorter as _EnhancedFaceSorter
from backend import service

BG='#0a0b0f'; PANEL='#12151c'; PANEL2='#181c25'; CARD='#151922'; BORDER='#252b36'
TEXT='#f7f8fb'; MUTED='#8d96a6'; ACCENT='#8b5cf6'; WHITE='#ffffff'; DANGER='#ef4444'

class EnhancedFaceSorter(_EnhancedFaceSorter):
    def __init__(self):
        self._duplicate_groups=[]
        self._duplicate_busy=False
        super().__init__()
        # Add the duplicate tool to the existing bottom action bar created by v6.
        if hasattr(self,'selection_label'):
            bar=self.selection_label.master
            self.button(bar,'Find duplicates',self.find_duplicates).pack(side='left',padx=4)

    def find_duplicates(self):
        if self._duplicate_busy:
            return messagebox.showinfo('Duplicates','A duplicate scan is already running.')
        win=tk.Toplevel(self); win.title('Duplicate photos'); win.geometry('1100x720'); win.minsize(760,520); win.configure(bg=BG); win.transient(self)
        head=tk.Frame(win,bg=BG); head.pack(fill='x',padx=24,pady=(20,10))
        tk.Label(head,text='Duplicate photos',bg=BG,fg=TEXT,font=('Segoe UI',21,'bold')).pack(anchor='w')
        info=tk.Label(head,text='Exact duplicates only — files with identical contents. One copy will be kept per group.',bg=BG,fg=MUTED,font=('Segoe UI',9)); info.pack(anchor='w',pady=(3,0))
        status=tk.Label(win,text='Ready to scan your indexed photos.',bg=BG,fg=MUTED,font=('Segoe UI',9)); status.pack(fill='x',padx=24,pady=(0,8))
        body=tk.Frame(win,bg=BG); body.pack(fill='both',expand=True,padx=24)
        text=tk.Text(body,bg=PANEL,fg=TEXT,insertbackground=TEXT,relief='flat',bd=0,font=('Consolas',9),wrap='word')
        scroll=tk.Scrollbar(body,orient='vertical',command=text.yview); text.configure(yscrollcommand=scroll.set); text.pack(side='left',fill='both',expand=True); scroll.pack(side='right',fill='y')
        foot=tk.Frame(win,bg=BG); foot.pack(fill='x',padx=24,pady=16)
        delete_btn=tk.Button(foot,text='Remove duplicates',state='disabled',bg=DANGER,fg=WHITE,activebackground='#dc2626',activeforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',10,'bold'),padx=15,pady=9)
        delete_btn.pack(side='right')
        scan_btn=tk.Button(foot,text='Scan for duplicates',bg=ACCENT,fg=WHITE,activebackground='#7c3aed',activeforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',10,'bold'),padx=15,pady=9); scan_btn.pack(side='right',padx=8)
        close_btn=tk.Button(foot,text='Close',command=win.destroy,bg=PANEL2,fg=WHITE,activebackground='#202633',activeforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',9,'bold'),padx=15,pady=9); close_btn.pack(side='left')

        def render(groups):
            text.configure(state='normal'); text.delete('1.0','end')
            if not groups:
                text.insert('end','No exact duplicate files were found.\n\nFiles that only look similar are not included in this scan.'); text.configure(state='disabled'); delete_btn.configure(state='disabled'); return
            duplicate_count=sum(len(g['duplicates']) for g in groups)
            total_bytes=sum(g['size']*len(g['duplicates']) for g in groups)
            text.insert('end',f'Found {len(groups):,} duplicate group(s) — {duplicate_count:,} removable copy/copies — {self._format_bytes(total_bytes)} reclaimable.\n\n')
            for n,g in enumerate(groups,1):
                text.insert('end',f'GROUP {n}  •  {g["count"]} identical files  •  {self._format_bytes(g["size"])} each\n')
                text.insert('end',f'  KEEP    {g["keep"]}\n')
                for p in g['duplicates']: text.insert('end',f'  REMOVE  {p}\n')
                text.insert('end','\n')
            text.configure(state='disabled'); delete_btn.configure(state='normal')

        def scan_worker():
            self._duplicate_busy=True
            def busy(): scan_btn.configure(state='disabled'); delete_btn.configure(state='disabled'); status.configure(text='Scanning file contents for exact duplicates…')
            self.after(0,busy)
            try:
                groups=service.find_duplicate_photos(); self._duplicate_groups=groups
                self.after(0,lambda g=groups: (render(g),status.configure(text=f'Found {len(g):,} duplicate group(s). Review the KEEP/REMOVE list before deleting.')))
            except Exception as e:
                self.after(0,lambda e=e:messagebox.showerror('Duplicate scan failed',str(e),parent=win))
                self.after(0,lambda:status.configure(text='Duplicate scan failed.'))
            finally:
                self._duplicate_busy=False
                self.after(0,lambda:scan_btn.configure(state='normal'))
        def start_scan():
            if not self._duplicate_busy:
                threading.Thread(target=scan_worker,daemon=True).start()
        # Import here to keep startup imports unchanged.
        import threading
        scan_btn.configure(command=start_scan)

        def remove_all():
            groups=list(self._duplicate_groups)
            count=sum(len(g['duplicates']) for g in groups)
            if not count:return
            reclaim=sum(g['size']*len(g['duplicates']) for g in groups)
            ok=messagebox.askyesno('Remove duplicate photos',f'Permanently delete {count:,} duplicate file(s)?\n\nOne copy in each duplicate group will be kept.\n\nSpace to reclaim: {self._format_bytes(reclaim)}\n\nThis removes the duplicate files from your drive. Your kept originals are not modified.',parent=win)
            if not ok:return
            delete_btn.configure(state='disabled'); scan_btn.configure(state='disabled'); status.configure(text='Removing duplicate files…')
            def worker():
                try:
                    result=service.remove_duplicate_photos(groups); self._duplicate_groups=[]
                    def done():
                        render([]); self.group_signature=[]; self.render_gallery(); self.refresh();
                        status.configure(text=f'Removed {result["removed"]:,} duplicate file(s).')
                        if result.get('failed'):messagebox.showwarning('Some files were not removed',f'{len(result["failed"]):,} file(s) could not be removed.',parent=win)
                    self.after(0,done)
                except Exception as e:self.after(0,lambda e=e:messagebox.showerror('Remove duplicates failed',str(e),parent=win))
                finally:self.after(0,lambda:scan_btn.configure(state='normal'))
            threading.Thread(target=worker,daemon=True).start()
        delete_btn.configure(command=remove_all)
        win.after(80,start_scan)

    @staticmethod
    def _format_bytes(value):
        value=float(value)
        for unit in ('B','KB','MB','GB','TB'):
            if value<1024 or unit=='TB':return f'{value:.1f} {unit}'
            value/=1024

if __name__=='__main__': EnhancedFaceSorter().mainloop()
