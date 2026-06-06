from __future__ import annotations

from .ui_helpers import reset_tk_var, clear_text_widget, clear_tree_selection


class AdminViewManagerMixin:
    def clear_admin_selection(self) -> None:
        """Leert Admin-Detailbereich, bis ein Upload aktiv ausgewählt wird."""
        if not getattr(self, "legacy_admin_table_is_active", lambda: False)():
            if hasattr(self, "clear_file_view_selection"):
                self.clear_file_view_selection()
            return
        if hasattr(self, "admin_tree"):
            clear_tree_selection(self.admin_tree)
        if hasattr(self, "admin_preview_label"):
            self.admin_preview_image = None
            self.admin_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        if hasattr(self, "admin_show_persons_check"):
            self.admin_show_persons_check.grid_remove()
        if hasattr(self, "admin_person_legend_frame"):
            self.admin_person_legend_frame.grid_remove()
        if hasattr(self, "admin_person_legend_text"):
            clear_text_widget(self.admin_person_legend_text, disable_after=True)
        if hasattr(self, "admin_meta_vars"):
            for var in self.admin_meta_vars.values():
                reset_tk_var(var)
        for attr in ("admin_description_text", "admin_note_text", "admin_json_text"):
            widget = getattr(self, attr, None)
            if widget is not None:
                clear_text_widget(widget, "Keine Datei ausgewählt." if attr == "admin_json_text" else None, disable_after=True)
        if hasattr(self, "admin_new_filename_var"):
            self.admin_new_filename_var.set("")
        if hasattr(self, "new_status_var"):
            self.new_status_var.set("")
        if hasattr(self, "admin_document_points_var"):
            self.admin_document_points_var.set("keine Datei ausgewählt")
        if hasattr(self, "update_admin_openai_controls"):
            self.update_admin_openai_controls()
