from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

from PIL import Image, ImageTk

from .models import PersonMark


class PersonTagger(tk.Toplevel):
    def __init__(self, master: tk.Misc, image_path: Path, initial_persons: list[dict] | None = None):
        super().__init__(master)
        self.title("Personen markieren")
        self.geometry("1000x700")
        self.image_path = image_path
        self.persons: list[PersonMark] = []
        if initial_persons:
            for idx, data in enumerate(initial_persons, start=1):
                try:
                    self.persons.append(PersonMark(
                        number=int(data.get("number") or idx),
                        x=float(data.get("x", 0)),
                        y=float(data.get("y", 0)),
                        display_name=str(data.get("display_name") or data.get("name") or ""),
                        certainty=str(data.get("certainty") or "unbekannt"),
                        note=str(data.get("note") or ""),
                    ))
                except Exception:
                    continue
            for idx, p in enumerate(self.persons, start=1):
                p.number = idx
        self._result: list[PersonMark] | None = None

        self.original_image = Image.open(image_path)
        self.display_image = self.original_image.copy()
        self.photo: ImageTk.PhotoImage | None = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg="#222222")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        side = ttk.Frame(self)
        side.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        side.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(side, columns=("name", "certainty", "note"), show="headings", height=18)
        self.tree.heading("name", text="Name")
        self.tree.heading("certainty", text="Sicherheit")
        self.tree.heading("note", text="Bemerkung")
        self.tree.grid(row=0, column=0, sticky="nsew")

        btn_frame = ttk.Frame(side)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btn_frame, text="Ausgewählte Markierung bearbeiten", command=self.edit_selected).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Ausgewählte Markierung löschen", command=self.delete_selected).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Fertig", command=self.finish).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Abbrechen", command=self.cancel).pack(fill="x", pady=2)

        self.bind("<Configure>", lambda _event: self.redraw())
        self.after(100, self.redraw)
        self.grab_set()

    def redraw(self) -> None:
        width = max(self.canvas.winfo_width(), 100)
        height = max(self.canvas.winfo_height(), 100)
        img_w, img_h = self.original_image.size
        self.scale = min(width / img_w, height / img_h)
        new_w = max(1, int(img_w * self.scale))
        new_h = max(1, int(img_h * self.scale))
        self.offset_x = (width - new_w) // 2
        self.offset_y = (height - new_h) // 2

        self.display_image = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(self.display_image)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.photo)

        for p in self.persons:
            x = self.offset_x + int(p.x * new_w)
            y = self.offset_y + int(p.y * new_h)
            self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, fill="white", outline="black", width=2)
            self.canvas.create_text(x, y, text=str(p.number), fill="black", font=("Arial", 11, "bold"))

    def on_canvas_click(self, event: tk.Event) -> None:
        img_w, img_h = self.display_image.size
        if event.x < self.offset_x or event.y < self.offset_y:
            return
        if event.x > self.offset_x + img_w or event.y > self.offset_y + img_h:
            return

        rel_x = (event.x - self.offset_x) / img_w
        rel_y = (event.y - self.offset_y) / img_h
        number = len(self.persons) + 1

        name = simpledialog.askstring("Person", f"Name für Person {number}:", parent=self)
        if name is None:
            return
        certainty = simpledialog.askstring("Sicherheit", "sicher / vermutlich / unbekannt:", initialvalue="unbekannt", parent=self)
        if certainty is None:
            return
        note = simpledialog.askstring("Bemerkung", "Bemerkung:", parent=self)
        if note is None:
            return

        mark = PersonMark(number=number, x=rel_x, y=rel_y, display_name=name, certainty=certainty or "unbekannt", note=note)
        self.persons.append(mark)
        self.refresh_tree()
        self.redraw()

    def refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in self.persons:
            self.tree.insert("", "end", iid=str(p.number), values=(f"{p.number}: {p.display_name}", p.certainty, p.note))


    def edit_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst eine Personenmarkierung auswählen.", parent=self)
            return
        number = int(selected[0])
        person = next((p for p in self.persons if p.number == number), None)
        if person is None:
            return
        name = simpledialog.askstring("Person", f"Name für Person {number}:", initialvalue=person.display_name, parent=self)
        if name is None:
            return
        certainty = simpledialog.askstring("Sicherheit", "sicher / vermutlich / unbekannt:", initialvalue=person.certainty or "unbekannt", parent=self)
        if certainty is None:
            return
        note = simpledialog.askstring("Bemerkung", "Bemerkung:", initialvalue=person.note or "", parent=self)
        if note is None:
            return
        person.display_name = name
        person.certainty = certainty or "unbekannt"
        person.note = note
        self.refresh_tree()
        self.redraw()

    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        numbers = {int(iid) for iid in selected}
        self.persons = [p for p in self.persons if p.number not in numbers]
        for idx, p in enumerate(self.persons, start=1):
            p.number = idx
        self.refresh_tree()
        self.redraw()

    def finish(self) -> None:
        self._result = self.persons
        self.destroy()

    def cancel(self) -> None:
        if messagebox.askyesno("Abbrechen", "Personenerfassung wirklich verwerfen?", parent=self):
            self._result = None
            self.destroy()

    def show_modal(self) -> list[PersonMark] | None:
        self.wait_window()
        return self._result
