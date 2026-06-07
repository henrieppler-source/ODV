from __future__ import annotations

from .ui_helpers import reset_tk_var, clear_text_widget, clear_tree_selection


class AdminViewManagerMixin:
    def clear_admin_selection(self) -> None:
        """Leert Admin-Detailbereich, bis ein Upload aktiv ausgewählt wird."""
        self.clear_file_view_selection()
        clear_tree_selection(self.admin_tree)
        self.admin_preview_image = None
        self.admin_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        self.admin_show_persons_check.grid_remove()
        self.admin_person_legend_frame.grid_remove()
        clear_text_widget(self.admin_person_legend_text, disable_after=True)
        for var in self.admin_meta_vars.values():
            reset_tk_var(var)
        for attr in ("admin_description_text", "admin_note_text", "admin_json_text"):
            clear_text_widget(self.admin_description_text if attr == "admin_description_text" else self.admin_note_text if attr == "admin_note_text" else self.admin_json_text, "Keine Datei ausgewählt." if attr == "admin_json_text" else None, disable_after=True)
        self.admin_new_filename_var.set("")
        self.new_status_var.set("")
        self.admin_document_points_var.set("keine Datei ausgewählt")
        self.update_admin_openai_controls()
