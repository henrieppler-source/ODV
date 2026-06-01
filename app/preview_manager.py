from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from .file_service import is_image_file


class PreviewManagerMixin:
    def set_file_legend(self, lines: list[str]) -> None:
        if hasattr(self, "person_legend_text"):
            self.person_legend_text.configure(state="normal")
            self.person_legend_text.delete("1.0", "end")
            self.person_legend_text.insert("1.0", "\n".join(lines) if lines else "")
            self.person_legend_text.configure(state="disabled")

    def hide_file_person_ui(self) -> None:
        if hasattr(self, "person_legend_frame"):
            self.person_legend_frame.grid_remove()
        if hasattr(self, "show_persons_check"):
            self.show_persons_check.grid_remove()
        self.set_file_legend([])

    def show_file_preview(self) -> None:
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir():
            self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
            self.hide_file_person_ui()
            return
        if not is_image_file(path):
            self.file_preview_label.configure(image="", text=f"Keine Bildvorschau für:\n{path.name}")
            self.hide_file_person_ui()
            return
        persons = []
        if self.file_view_current_metadata:
            persons = self.file_view_current_metadata.get("persons", []) or []
        has_persons = bool(persons)
        if hasattr(self, "show_persons_check"):
            if has_persons:
                self.show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
                self.show_persons_check.configure(state="normal")
            else:
                self.show_persons_check.grid_remove()
        if hasattr(self, "person_legend_frame"):
            if has_persons and self.show_persons_var.get():
                self.person_legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
            else:
                self.person_legend_frame.grid_remove()
        try:
            img = Image.open(path).convert("RGB")
            max_w = max(500, self.file_preview_label.winfo_width() - 20)
            max_h = max(260, self.file_preview_label.winfo_height() - 20)
            img.thumbnail((max_w, max_h))
            img, legend_lines = self.draw_person_overlays(img, persons, has_persons and self.show_persons_var.get(), font_size=14)
            self.set_file_legend(legend_lines if has_persons and self.show_persons_var.get() else [])
            self.file_preview_image = ImageTk.PhotoImage(img)
            self.file_preview_label.configure(image=self.file_preview_image, text="")
        except Exception as exc:
            self.file_preview_label.configure(image="", text=f"Vorschaufehler:\n{exc}")
            self.hide_file_person_ui()

    def set_admin_legend(self, lines: list[str]) -> None:
        if hasattr(self, "admin_person_legend_text"):
            self.admin_person_legend_text.configure(state="normal")
            self.admin_person_legend_text.delete("1.0", "end")
            self.admin_person_legend_text.insert("1.0", "\n".join(lines) if lines else "Keine Personenangaben.")
            self.admin_person_legend_text.configure(state="disabled")

    def hide_admin_person_ui(self) -> None:
        if hasattr(self, "admin_person_legend_frame"):
            self.admin_person_legend_frame.grid_remove()
        if hasattr(self, "admin_show_persons_check"):
            self.admin_show_persons_check.grid_remove()
        self.set_admin_legend([])

    def show_admin_preview(self, item: dict) -> None:
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        if not path or not path.exists() or path.is_dir():
            if hasattr(self, "admin_preview_label"):
                message = "Keine Datei ausgewählt." if not item else "Datei nicht gefunden."
                self.admin_preview_label.configure(image="", text=message)
            self.hide_admin_person_ui()
            return
        if not is_image_file(path):
            if hasattr(self, "admin_preview_label"):
                self.admin_preview_label.configure(image="", text=f"Keine Bildvorschau für:\n{path.name}")
            self.hide_admin_person_ui()
            return
        persons = item.get("persons", []) or []
        has_persons = bool(persons)
        if hasattr(self, "admin_show_persons_check"):
            if has_persons:
                self.admin_show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
                self.admin_show_persons_check.configure(state="normal")
            else:
                self.admin_show_persons_check.grid_remove()
        show_persons = has_persons and bool(getattr(self, "admin_show_persons_var", tk.BooleanVar(value=True)).get())
        if hasattr(self, "admin_person_legend_frame"):
            if show_persons:
                self.admin_person_legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
            else:
                self.admin_person_legend_frame.grid_remove()
        try:
            img = Image.open(path).convert("RGB")
            max_w = max(420, self.admin_preview_label.winfo_width() - 20)
            max_h = max(260, self.admin_preview_label.winfo_height() - 20)
            img.thumbnail((max_w, max_h))
            img, legend_lines = self.draw_person_overlays(img, persons, show_persons, font_size=13)
            self.set_admin_legend(legend_lines if show_persons else [])
            self.admin_preview_image = ImageTk.PhotoImage(img)
            self.admin_preview_label.configure(image=self.admin_preview_image, text="")
        except Exception as exc:
            self.admin_preview_label.configure(image="", text=f"Vorschaufehler:\n{exc}")
            self.hide_admin_person_ui()
