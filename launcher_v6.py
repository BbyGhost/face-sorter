"""Face Sorter v3.3.4 - reliable person photo browser.
Uses a main-thread queue for Tk updates and lazy thumbnail loading so large
person groups render correctly without freezing or losing PhotoImage refs.
"""
from __future__ import annotations
import os, queue, threading, tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps
from launcher_v4 import EnhancedFaceSorter as _EnhancedFaceSorter
from backend import service

BG='#0a0b0f'; PANEL='#12151c'; PANEL2='#181c25'; CARD='#151922'; BORDER='#252b36'
TEXT='#f7f8fb'; MUTED='#8d96a6'; ACCENT='#8b5cf6'; WHITE='#ffffff'

class EnhancedFaceSorter(_EnhancedFaceSorter):
    def open_person(self, person_id):
        person_id=int(person_id)
        group=next((g for g in self.groups if int(g['id'])==person_id),None)
        if not group:
            messagebox.showinfo('Person','This person group is no longer available.'); return
        paths=service.person_images(person_id)
        if not paths:
            messagebox.showinfo('Person','No photos are currently assigned to this person.'); return

        win=tk.Toplevel(self); win.title(f"{group['name']} — {len(paths):,} photos")
        win.geometry('1200x820'); win.minsize(820,620); win.configure(bg=BG); win.transient(self)
        header=tk.Frame(win,bg=BG); header.pack(fill='x',padx=24,pady=(20,12))
        left=tk.Frame(header,bg=BG); left.pack(side='left',fill='x',expand=True)
        tk.Label(left,text=str(group['name']),bg=BG,fg=TEXT,font=('Segoe UI',22,'bold')).pack(anchor='w')
        tk.Label(left,text=f"{len(paths):,} photos • Double-click a photo to open the original",bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(3,0))
        tk.Button(header,text='Open folder',command=lambda:self._open_person_folder(paths),bg=PANEL2,fg=WHITE,activebackground='#202633',activeforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',10,'bold'),padx=16,pady=9).pack(side='right')

        host=tk.Frame(win,bg=BG); host.pack(fill='both',expand=True,padx=24,pady=(0,18))
        canvas=tk.Canvas(host,bg=BG,highlightthickness=0,bd=0)
        bar=tk.Scrollbar(host,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set); canvas.pack(side='left',fill='both',expand=True); bar.pack(side='right',fill='y')
        canvas.bind('<MouseWheel>',lambda e:canvas.yview_scroll(int(-e.delta/120),'units'))
        inner=tk.Frame(canvas,bg=BG); window_id=canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window_id,width=max(e.width,760)))

        state={'photos':{},'cards':{},'next':0,'cols':6,'queue':queue.Queue(),'loading':set()}
        thumb_w,thumb_h=180,150
        def cols_now(): return max(3,min(6,max(3,canvas.winfo_width()//195)))
        def add_card(index,path,image,error=None):
            if not win.winfo_exists(): return
            cols=state['cols']; row,col=divmod(index,cols)
            card=tk.Frame(inner,bg=CARD,highlightthickness=1,highlightbackground=BORDER)
            card.grid(row=row,column=col,padx=6,pady=6,sticky='nsew')
            if image is not None:
                photo=ImageTk.PhotoImage(image)
                state['photos'][index]=photo
                label=tk.Label(card,image=photo,bg=PANEL2,width=thumb_w,height=thumb_h)
            else:
                label=tk.Label(card,text='Preview unavailable',bg=PANEL2,fg=MUTED,width=24,height=9,font=('Segoe UI',9))
                if error: label.bind('<Enter>',lambda e:tip.config(text=error))
            label.pack(padx=5,pady=5)
            name=os.path.basename(path)
            tk.Label(card,text=name,bg=CARD,fg=TEXT,font=('Segoe UI',8),anchor='w',width=25).pack(padx=7,anchor='w')
            label.bind('<Double-Button-1>',lambda e,p=path:self._open_original(p))
            card.bind('<Double-Button-1>',lambda e,p=path:self._open_original(p))
            state['cards'][index]=card

        def worker(index,path):
            try:
                with Image.open(path) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((thumb_w,thumb_h),Image.Resampling.LANCZOS)
                    image=im.copy()
                state['queue'].put((index,path,image,None))
            except Exception as e:
                state['queue'].put((index,path,None,str(e)))

        def pump():
            if not win.winfo_exists(): return
            try:
                for _ in range(10):
                    index,path,image,error=state['queue'].get_nowait()
                    state['loading'].discard(index); add_card(index,path,image,error)
            except queue.Empty: pass
            win.after(30,pump)

        def start_visible():
            # Load a small lead window first, then the rest. This keeps the UI responsive.
            lead=min(len(paths),max(30,state['cols']*6))
            for i in range(lead):
                if i not in state['loading']:
                    state['loading'].add(i); threading.Thread(target=worker,args=(i,paths[i]),daemon=True).start()
            def rest():
                for i in range(lead,len(paths)):
                    if i not in state['loading']:
                        state['loading'].add(i); threading.Thread(target=worker,args=(i,paths[i]),daemon=True).start()
            threading.Thread(target=rest,daemon=True).start()

        # Build the grid only from queued results; all Tk operations happen on this thread.
        state['cols']=cols_now()
        for c in range(6): inner.grid_columnconfigure(c,weight=1)
        tip=tk.Label(win,text='',bg=BG,fg=MUTED,font=('Segoe UI',8)); tip.pack(side='bottom',anchor='w',padx=24,pady=(0,4))
        win.after(30,pump)
        win.after(80,start_visible)

    def _open_original(self,path):
        try:
            if os.path.exists(path): os.startfile(path)
            else: messagebox.showwarning('Photo unavailable',f'The original file no longer exists:\n\n{path}')
        except Exception as e: messagebox.showerror('Open photo',str(e))

    def _open_person_folder(self,paths):
        existing=[p for p in paths if os.path.exists(p)]
        if not existing:
            messagebox.showwarning('Folder unavailable',"None of this person's original photos could be found."); return
        try: os.startfile(os.path.dirname(existing[0]))
        except Exception as e: messagebox.showerror('Open folder',str(e))

if __name__=='__main__': EnhancedFaceSorter().mainloop()
