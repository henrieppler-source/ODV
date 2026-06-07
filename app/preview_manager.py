from __future__ import annotations

from PIL import Image, ImageTk

from .file_service import is_image_file


class PreviewManagerMixin:
    def on_file_preview_mousewheel(self, event) -> str:
        path = self.file_view_current_path
        if not path or not path.exists() or not is_image_file(path):
            return "break"
        try:
            delta = event.delta
        except Exception:
            delta = 0
        if delta == 0:
            try:
                delta = 120 if event.num == 4 else -120
            except Exception:
                delta = 0
        if not delta:
            return "break"
        factor = 1.12 if delta > 0 else 1 / 1.12
        current = float(self.file_preview_zoom or 1.0)
        self.file_preview_zoom = max(0.3, min(4.0, current * factor))
        self.show_file_preview()
        return "break"

    def set_file_legend(self, lines: list[str]) -> None:
        self.person_legend_text.configure(state="normal")
        self.person_legend_text.delete("1.0", "end")
        self.person_legend_text.insert("1.0", "\n".join(lines) if lines else "")
        self.person_legend_text.configure(state="disabled")

    def hide_file_person_ui(self) -> None:
        self.person_legend_frame.grid_remove()
        self.show_persons_check.grid_remove()
        self.set_file_legend([])

    def show_file_preview(self) -> None:
        path = self.file_view_current_path
        self.update_file_view_preview_tab_visibility()
        if not path or not path.exists() or path.is_dir():
            self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
            self.hide_file_person_ui()
            return
        if not is_image_file(path):
            self.file_preview_label.configure(image="", text="")
            self.hide_file_person_ui()
            return
        persons = []
        if self.file_view_current_metadata:
            persons = self.file_view_current_metadata.get("persons", []) or []
        has_persons = bool(persons)
        if has_persons:
            self.show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
            self.show_persons_check.configure(state="normal")
        else:
            self.show_persons_check.grid_remove()
        if has_persons and self.show_persons_var.get():
            self.person_legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        else:
            self.person_legend_frame.grid_remove()
        try:
            img = Image.open(path).convert("RGB")
            zoom = float(self.file_preview_zoom or 1.0)
            max_w = int(max(500, self.file_preview_label.winfo_width() - 20) * zoom)
            max_h = int(max(260, self.file_preview_label.winfo_height() - 20) * zoom)
            img.thumbnail((max_w, max_h))
            img, legend_lines = self.draw_person_overlays(img, persons, has_persons and self.show_persons_var.get(), font_size=14)
            self.set_file_legend(legend_lines if has_persons and self.show_persons_var.get() else [])
            self.file_preview_image = ImageTk.PhotoImage(img)
            self.file_preview_label.configure(image=self.file_preview_image, text="")
        except Exception as exc:
            self.file_preview_label.configure(image="", text=f"Vorschaufehler:\n{exc}")
            self.hide_file_person_ui()

    def set_admin_legend(self, lines: list[str]) -> None:
        self.admin_person_legend_text.configure(state="normal")
        self.admin_person_legend_text.delete("1.0", "end")
        self.admin_person_legend_text.insert("1.0", "\n".join(lines) if lines else "Keine Personenangaben.")
        self.admin_person_legend_text.configure(state="disabled")

    def hide_admin_person_ui(self) -> None:
        self.admin_person_legend_frame.grid_remove()
        self.admin_show_persons_check.grid_remove()
        self.set_admin_legend([])

    def show_admin_preview(self, item: dict) -> None:
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        if not path or not path.exists() or path.is_dir():
            message = "Keine Datei ausgewählt." if not item else "Datei nicht gefunden."
            self.admin_preview_label.configure(image="", text=message)
            self.hide_admin_person_ui()
            return
        if not is_image_file(path):
            self.admin_preview_label.configure(image="", text=f"Keine Bildvorschau für:\n{path.name}")
            self.hide_admin_person_ui()
            return
        persons = item.get("persons", []) or []
        has_persons = bool(persons)
        if has_persons:
            self.admin_show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
            self.admin_show_persons_check.configure(state="normal")
        else:
            self.admin_show_persons_check.grid_remove()
        show_persons = has_persons and self.admin_show_persons_var.get()
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
