from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from .models import PersonMark


CERTAINTY_OPTIONS = [
    "sicher",
    "vermutlich",
    "unbekannt",
    "persönlich bekannt",
]


class PersonTagger(tk.Toplevel):
    def __init__(self, master: tk.Misc, image_path: Path, initial_persons: list[dict] | None = None):
        super().__init__(master)
        self.title("Personen markieren")
        self.geometry("1000x700")
        self.image_path = image_path
        self.persons: list[PersonMark] = []
        if initial_persons:
            used_numbers: set[int] = set()
            for idx, data in enumerate(initial_persons, start=1):
                try:
                    number = int(data.get("number") or idx)
                    if number <= 0 or number in used_numbers:
                        number = 1
                        while number in used_numbers:
                            number += 1
                    used_numbers.add(number)
                    self.persons.append(PersonMark(
                        number=number,
                        x=float(data.get("x", 0)),
                        y=float(data.get("y", 0)),
                        display_name=str(data.get("display_name") or data.get("name") or ""),
                        certainty=str(data.get("certainty") or "unbekannt"),
                        note=str(data.get("note") or ""),
                    ))
                except Exception:
                    continue
        self._result: list[PersonMark] | None = None
        self.selected_number: int | None = None
        self.pending_mark: PersonMark | None = None
        self._drag_mark: PersonMark | None = None
        self._drag_start: tuple[int, int] | None = None
        self._dragged = False
        self._drag_threshold = 6
        self._pending_new: tuple[float, float] | None = None
        self._current_number_var = tk.StringVar(value=f"Nächste Markierung: {self.next_person_number()}")

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
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-1>", self.on_canvas_double_click)

        side = ttk.Frame(self)
        side.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        side.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(side, columns=("number", "name", "certainty", "note"), show="headings", height=18)
        self.tree.heading("number", text="Nr.")
        self.tree.heading("name", text="Name")
        self.tree.heading("certainty", text="Nachweis")
        self.tree.heading("note", text="Bemerkung")
        self.tree.column("number", width=52, anchor="center", stretch=False)
        self.tree.column("name", width=150, anchor="w")
        self.tree.column("certainty", width=110, anchor="w", stretch=False)
        self.tree.column("note", width=180, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        ttk.Label(side, textvariable=self._current_number_var, foreground="#555555").grid(row=1, column=0, sticky="w", pady=(6, 0))
        btn_frame = ttk.Frame(side)
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
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

        marks = list(self.persons)
        if self.pending_mark is not None:
            marks.append(self.pending_mark)
        for p in marks:
            x = self.offset_x + int(p.x * new_w)
            y = self.offset_y + int(p.y * new_h)
            is_selected = p.number == self.selected_number
            is_pending = self.pending_mark is not None and p.number == self.pending_mark.number
            radius = 18 if is_selected or is_pending else 12
            fill = "#ffe680" if is_selected or is_pending else "white"
            outline = "#d00000" if is_selected or is_pending else "black"
            width_line = 4 if is_selected or is_pending else 2
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=width_line)
            self.canvas.create_text(x, y, text=str(p.number), fill="black", font=("Arial", 13 if is_selected or is_pending else 11, "bold"))

    def next_person_number(self) -> int:
        used = {p.number for p in self.persons if p.number > 0}
        number = 1
        while number in used:
            number += 1
        return number

    def update_current_number_hint(self, number: int | None = None, selected: bool = False) -> None:
        number = number or self.next_person_number()
        prefix = "Markierung" if selected else "Nächste Markierung"
        self._current_number_var.set(f"{prefix}: {number}")

    def on_tree_select(self, _event: tk.Event | None = None) -> None:
        selected = self.tree.selection()
        if not selected:
            self.selected_number = None
            self.update_current_number_hint()
        else:
            try:
                self.selected_number = int(selected[0])
                self.update_current_number_hint(self.selected_number, selected=True)
            except Exception:
                self.selected_number = None
        self.pending_mark = None
        self.redraw()

    def edit_person_dialog(
        self,
        *,
        number: int,
        title: str,
        name: str = "",
        certainty: str = "unbekannt",
        note: str = "",
    ) -> tuple[str, str, str] | None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("540x380")
        dialog.transient(self)
        dialog.resizable(True, True)

        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(3, weight=1)

        ttk.Label(dialog, text=f"Markierung {number}", font=("", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))
        ttk.Label(dialog, text="Name:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        name_var = tk.StringVar(value=name)
        name_entry = ttk.Entry(dialog, textvariable=name_var)
        name_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=4)

        ttk.Label(dialog, text="Nachweis:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        certainty_var = tk.StringVar(value=certainty or "unbekannt")
        certainty_combo = ttk.Combobox(dialog, textvariable=certainty_var, values=CERTAINTY_OPTIONS, state="readonly")
        certainty_combo.grid(row=2, column=1, sticky="ew", padx=12, pady=4)

        ttk.Label(dialog, text="Bemerkung:").grid(row=3, column=0, sticky="nw", padx=12, pady=4)
        note_text = tk.Text(dialog, height=6, wrap="word")
        note_text.grid(row=3, column=1, sticky="nsew", padx=12, pady=4)
        note_text.insert("1.0", note or "")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))

        result: dict[str, tuple[str, str, str] | None] = {"value": None}

        def on_ok() -> None:
            person_name = name_var.get().strip()
            if not person_name:
                messagebox.showwarning("Person", "Bitte einen Namen angeben.", parent=dialog)
                name_entry.focus_set()
                return
            result["value"] = (
                person_name,
                certainty_var.get().strip() or "unbekannt",
                note_text.get("1.0", "end-1c").strip(),
            )
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok).pack(side="left", padx=4)
        ttk.Button(button_frame, text="Abbrechen", command=on_cancel).pack(side="left", padx=4)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        name_entry.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        return result["value"]

    def on_canvas_press(self, event: tk.Event) -> None:
        img_w, img_h = self.display_image.size
        if event.x < self.offset_x or event.y < self.offset_y:
            return
        if event.x > self.offset_x + img_w or event.y > self.offset_y + img_h:
            return

        existing_mark = self.find_mark_at_position(event.x, event.y, img_w, img_h)
        if existing_mark is not None:
            self.pending_mark = None
            self.selected_number = existing_mark.number
            self.update_current_number_hint(existing_mark.number, selected=True)
            try:
                self.tree.selection_set(str(existing_mark.number))
                self.tree.see(str(existing_mark.number))
            except Exception:
                pass
            self.redraw()
            self._drag_mark = existing_mark
            self._drag_start = (event.x, event.y)
            self._dragged = False
            self._pending_new = None
            return

        rel_x = (event.x - self.offset_x) / img_w
        rel_y = (event.y - self.offset_y) / img_h
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))
        self._pending_new = (rel_x, rel_y)
        self._drag_mark = None
        self._drag_start = None
        self._dragged = False

    def on_canvas_motion(self, event: tk.Event) -> None:
        if self._drag_mark is None or self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        dist_sq = dx * dx + dy * dy
        if (not self._dragged) and dist_sq >= self._drag_threshold * self._drag_threshold:
            self._dragged = True
        if not self._dragged:
            return

        img_w, img_h = self.display_image.size
        if img_w <= 0 or img_h <= 0:
            return

        self._drag_mark.x = max(0.0, min(1.0, (event.x - self.offset_x) / img_w))
        self._drag_mark.y = max(0.0, min(1.0, (event.y - self.offset_y) / img_h))
        self.redraw()

    def on_canvas_release(self, event: tk.Event) -> None:
        if self._drag_mark is not None:
            if self._dragged:
                self._drag_mark = None
                self._drag_start = None
                self._dragged = False
                self.refresh_tree()
                self.redraw()
                return

            self._drag_mark = None
            self._drag_start = None
            self._dragged = False
            return

        if self._pending_new is None:
            return
        rel_x, rel_y = self._pending_new
        self._pending_new = None
        number = self.next_person_number()
        self.selected_number = number
        self.pending_mark = PersonMark(number=number, x=rel_x, y=rel_y, display_name="", certainty="unbekannt", note="")
        self.update_current_number_hint(number, selected=True)
        self.redraw()
        data = self.edit_person_dialog(number=number, title=f"Person {number} erfassen")
        if data is None:
            self.pending_mark = None
            self.selected_number = None
            self.update_current_number_hint()
            self.redraw()
            return
        name, certainty, note = data
        mark = PersonMark(number=number, x=rel_x, y=rel_y, display_name=name, certainty=certainty or "unbekannt", note=note)
        self.pending_mark = None
        self.persons.append(mark)
        self.refresh_tree()
        try:
            self.tree.selection_set(str(number))
            self.tree.see(str(number))
            self.selected_number = number
        except Exception:
            pass
        self.redraw()

    def on_canvas_double_click(self, event: tk.Event) -> None:
        img_w, img_h = self.display_image.size
        if event.x < self.offset_x or event.y < self.offset_y:
            return
        if event.x > self.offset_x + img_w or event.y > self.offset_y + img_h:
            return

        existing_mark = self.find_mark_at_position(event.x, event.y, img_w, img_h)
        if existing_mark is not None:
            self.edit_mark(existing_mark.number)

    def edit_mark(self, number: int) -> None:
        person = next((p for p in self.persons if p.number == number), None)
        if person is None:
            return
        self.selected_number = number
        self.update_current_number_hint(number, selected=True)
        self.redraw()
        data = self.edit_person_dialog(
            number=number,
            title=f"Person {number} bearbeiten",
            name=person.display_name,
            certainty=person.certainty,
            note=person.note,
        )
        if data is None:
            return
        name, certainty, note = data
        person.display_name = name
        person.certainty = certainty or "unbekannt"
        person.note = note
        self.refresh_tree()
        try:
            self.tree.selection_set(str(number))
            self.tree.see(str(number))
            self.selected_number = number
        except Exception:
            pass
        self.redraw()

    def find_mark_at_position(self, x: int, y: int, img_w: int, img_h: int) -> PersonMark | None:
        """Returns the first mark near a canvas click position."""
        for person in self.persons:
            px = self.offset_x + int(person.x * img_w)
            py = self.offset_y + int(person.y * img_h)
            hit_radius = 20
            if (x - px) ** 2 + (y - py) ** 2 <= hit_radius * hit_radius:
                return person
        return None

    def refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in sorted(self.persons, key=lambda person: person.number):
            self.tree.insert("", "end", iid=str(p.number), values=(p.number, p.display_name, p.certainty, p.note))
        self.update_current_number_hint()


    def edit_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst eine Personenmarkierung auswählen.", parent=self)
            return
        number = int(selected[0])
        self.edit_mark(number)

    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        numbers = {int(iid) for iid in selected}
        self.persons = [p for p in self.persons if p.number not in numbers]
        self.selected_number = None
        self.pending_mark = None
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
