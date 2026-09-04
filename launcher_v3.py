"""Face Sorter v3.3.1 compatibility launcher.
Adds the missing Rename action to the enhanced v3.3 gallery without changing the
stable base desktop source.
"""
import tkinter as tk
from tkinter import simpledialog, messagebox
from launcher_v2 import EnhancedFaceSorter
from backend import service

def rename_person(self):
    if len(self.selected_ids)!=1:
        messagebox.showinfo('Rename person','Select exactly one person first.')
        return
    ident=int(next(iter(self.selected_ids)))
    current=next((g['name'] for g in self.groups if int(g['id'])==ident),f'Person {ident}')
    name=simpledialog.askstring('Rename person','Person name:',initialvalue=current,parent=self)
    if not name or not name.strip(): return
    try:
        with service.DB_LOCK:
            service.DB.execute('UPDATE people SET name=? WHERE id=?',(name.strip(),ident))
            service.DB.commit()
        self.status.set(f'Renamed to {name.strip()}')
        self.refresh()
    except Exception as e:
        messagebox.showerror('Rename failed',str(e))

EnhancedFaceSorter.rename=rename_person

if __name__=='__main__':
    EnhancedFaceSorter().mainloop()
