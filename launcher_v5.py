"""Face Sorter v3.3.3 - person photo viewer.
Adds a real People -> person photo browser with thumbnails, scrolling,
open-in-Explorer, and double-click-to-open-original support.
"""
from __future__ import annotations
import os
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps
from launcher_v4 import EnhancedFaceSorter as _EnhancedFaceSorter
from backend import service

BG=_EnhancedFaceSorter.__mro__[1].BG if hasattr(_EnhancedFaceSorter.__mro__[1],'BG') else '#0a0b0f'
PANEL='#12151c'; PANEL2='#181c25'; CARD='#151922'; BORDER='#252b36'
TEXT='#f7f8fb'; MUTED='#8d96a6'; ACCENT='#8b5cf6'; WHITE='#ffffff'

class EnhancedFaceSorter(_EnhancedFaceSorter):
    def open_person(self, person_id):
        person_id=int(person_id)
        group=next((g for g in self.groups if int(g['id'])==person_id),None)
        if not group:
            messagebox.showinfo('Person','This person group is no longer available.')
            return
        paths=service.person_images(person_id)
        if not paths:
            messagebox.showinfo('Person','No photos are currently assigned to this person.')
            return

        win=tk.Toplevel(self)
        win.title(f"{group['name']} — {len(paths):,} photos")
        win.geometry('1180x780'); win.minsize(800,600); win.configure(bg=BG)
        win.transient(self)

        header=tk.Frame(win,bg=BG); header.pack(fill='x',padx=24,pady=(20,12))
        left=tk.Frame(header,bg=BG); left.pack(side='left',fill='x',expand=True)
        tk.Label(left,text=str(group['name']),bg=BG,fg=TEXT,font=('Segoe UI',22,'bold')).pack(anchor='w')
        tk.Label(left,text=f"{len(paths):,} photos • Double-click a photo to open the original",bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(3,0))
        tk.Button(header,text='Open folder',command=lambda:self._open_person_folder(paths),bg=PANEL2,fg=WHITE,activebackground='#202633',activeforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',10,'bold'),padx=16,pady=9).pack(side='right')

        host=tk.Frame(win,bg=BG); host.pack(fill='both',expand=True,padx=24,pady=(0,18))
        canvas=tk.Canvas(host,bg=BG,highlightthickness=0,bd=0)
        bar=tk.Scrollbar(host,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side='left',fill='both',expand=True); bar.pack(side='right',fill='y')
        canvas.bind('<MouseWheel>',lambda e:canvas.yview_scroll(int(-e.delta/120),'units'))

        inner=tk.Frame(canvas,bg=BG)
        window_id=canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window_id,width=max(e.width,760)))

        state={'photos':[],'buttons':[]}
        def load():
            for index,path in enumerate(paths):
                try:
                    with Image.open(path) as im:
                        im=ImageOps.exif_transpose(im).convert('RGB')
                        im.thumbnail((170,145),Image.Resampling.LANCZOS)
                        image=im.copy()
                    self.after(0,add_card,index,path,image)
                except Exception:
                    self.after(0,add_failed,index,path)

        def add_failed(index,path):
            if not win.winfo_exists(): return
            _add_photo_card(index,path,None)

        def add_card(index,path,image):
            if not win.winfo_exists(): return
            _add_photo_card(index,path,image)

        def _add_photo_card(index,path,image):
            cols=max(3,min(6,max(1,win.winfo_width()//190)))
            row,col=divmod(index,cols)
            while len(state['buttons'])<=index: state['buttons'].append(None)
            card=tk.Frame(inner,bg=CARD,highlightthickness=1,highlightbackground=BORDER)
            card.grid(row=row,column=col,padx=6,pady=6,sticky='nsew')
            if image is not None:
                photo=ImageTk.PhotoImage(image)
                state['photos'].append(photo)
                label=tk.Label(card,image=photo,bg=PANEL2,width=170,height=145)
            else:
                label=tk.Label(card,text='Preview unavailable',bg=PANEL2,fg=MUTED,width=23,height=9,font=('Segoe UI',9))
            label.pack(padx=5,pady=5)
            name=os.path.basename(path)
            tk.Label(card,text=name,bg=CARD,fg=TEXT,font=('Segoe UI',8),anchor='w',width=24).pack(padx=7,anchor='w')
            label.bind('<Double-Button-1>',lambda e,p=path:self._open_original(p))
            card.bind('<Double-Button-1>',lambda e,p=path:self._open_original(p))
            state['buttons'][index]=card

        def on_resize(_=None):
            # Cards are created using the current width. Existing windows are
            # intentionally kept stable to avoid destroying thumbnails.
            pass

        inner.grid_columnconfigure(tuple(range(6)),weight=1)
        win.bind('<Configure>',on_resize)
        threading.Thread(target=load,daemon=True).start()

    def _open_original(self,path):
        try:
            if os.path.exists(path): os.startfile(path)
            else: messagebox.showwarning('Photo unavailable',f'The original file no longer exists:\n\n{path}')
        except Exception as e:
            messagebox.showerror('Open photo',str(e))

    def _open_person_folder(self,paths):
        existing=[p for p in paths if os.path.exists(p)]
        if not existing:
            messagebox.showwarning('Folder unavailable','None of this person\'s original photos could be found.')
            return
        # Explorer opens the folder containing the first original photo.
        folder=os.path.dirname(existing[0])
        try: os.startfile(folder)
        except Exception as e: messagebox.showerror('Open folder',str(e))

if __name__=='__main__':
    EnhancedFaceSorter().mainloop()
