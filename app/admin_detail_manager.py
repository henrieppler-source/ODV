from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .api_client import ApiError
from .file_service import detect_document_type, make_normalized_archive_filename


class AdminDetailManagerMixin:
    def show_selected_admin_details(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        api_item = self.api_get_document_item(str(item.get("upload_id", ""))) if self.api_token else None
        if api_item:
            if item.get("_metadata_file") and not api_item.get("_metadata_file"):
                api_item["_metadata_file"] = item.get("_metadata_file")
            item.clear()
            item.update(api_item)
        self.normalize_admin_item_path_for_current_pc(item)
        resolved_path = self.resolve_document_local_path(item)
        if resolved_path and not item.get("document_type"):
            item["document_type"] = detect_document_type(resolved_path)
        self.update_admin_document_points_display(str(item.get("upload_id", "")))
        self.show_admin_preview(item)
        if hasattr(self, "admin_meta_vars"):
            self.refresh_admin_uploaded_by_options()
            if "uploaded_by" in self.admin_meta_vars and hasattr(self, "admin_uploaded_by_user_map"):
                uid = str(item.get("uploaded_by_user_id") or "")
                name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
                label = next((lbl for lbl, u in self.admin_uploaded_by_user_map.items() if str(u.get("id") or "") == uid), "")
                if not label:
                    label = next((lbl for lbl, u in self.admin_uploaded_by_user_map.items() if str(u.get("display_name") or u.get("name") or "") == name), name)
                try:
                    self.admin_meta_vars["uploaded_by"].set(label)
                except Exception:
                    pass
            for key, var in self.admin_meta_vars.items():
                if key == "uploaded_by" and self.is_current_admin():
                    continue
                value = item.get(key, "")
                if key == "transcription_done" and isinstance(var, tk.BooleanVar):
                    var.set(str(value).strip().lower() in {"1", "ja", "yes", "true", "x"})
                else:
                    var.set(str(value or ""))
            self.admin_description_text.delete("1.0", "end")
            self.admin_description_text.insert("1.0", str(item.get("description", "") or ""))
            if getattr(self, "admin_description_counter_var", None):
                self.update_description_counter(self.admin_description_text, self.admin_description_counter_var)
            self.admin_note_text.delete("1.0", "end")
            self.admin_note_text.insert("1.0", str(item.get("note", "") or ""))
        if hasattr(self, "admin_json_text"):
            self.admin_json_text.configure(state="normal")
            self.admin_json_text.delete("1.0", "end")
            view_item = {k: v for k, v in item.items() if k != "_metadata_file"}
            self.admin_json_text.insert("1.0", self.format_metadata_plain(view_item))
            self.admin_json_text.configure(state="disabled")
        if hasattr(self, "new_status_var"):
            self.new_status_var.set(self.normalize_document_status(item.get("status", "hochgeladen")))
        if hasattr(self, "admin_destination_combo"):
            self.refresh_admin_destination_choices()
        suggested = make_normalized_archive_filename(item, item.get("current_filename") or item.get("stored_filename") or item.get("original_filename", ""))
        self.admin_new_filename_var.set(suggested)
        self.configure_admin_actions_for_role()
        can_edit = self.can_edit_admin_item(item)
        if can_edit and self.api_token and item.get("upload_id"):
            try:
                self.api.lock_document(self.api_token, str(item.get("upload_id")))
            except ApiError as exc:
                can_edit = False
                if not getattr(self, "_last_lock_warning", "") == str(item.get("upload_id")):
                    self._last_lock_warning = str(item.get("upload_id"))
                    messagebox.showinfo("Dokument gesperrt", str(exc), parent=self)
        state = "normal" if can_edit else "disabled"
        for widget in list(getattr(self, "admin_meta_widgets", [])):
            try:
                if isinstance(widget, ttk.Combobox) and str(widget.cget("state")) == "readonly":
                    widget.configure(state="readonly" if can_edit else "disabled")
                else:
                    widget.configure(state=state)
            except Exception:
                pass
        for widget in (getattr(self, "admin_description_text", None), getattr(self, "admin_note_text", None)):
            if widget is not None:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass
        if hasattr(self, "admin_rename_button"):
            self.admin_rename_button.configure(state=("normal" if can_edit else "disabled"))
        self.remember_document_type(str(item.get("document_type", "")))

    def admin_save_metadata_fields(self, auto: bool = False) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        if not self.can_edit_admin_item(item):
            if not auto:
                messagebox.showwarning("Keine Berechtigung", "Dieses Dokument kann nicht bearbeitet werden.")
            return
        changed = []
        for key, var in getattr(self, "admin_meta_vars", {}).items():
            old = str(item.get(key, "") or "")
            raw_value = var.get()
            new = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
            if old != new:
                item[key] = new
                changed.append(f"{key}: {old} → {new}")
        for key, widget in [("description", getattr(self, "admin_description_text", None)), ("note", getattr(self, "admin_note_text", None))]:
            if widget is None:
                continue
            old = str(item.get(key, "") or "")
            new = widget.get("1.0", "end").strip()
            if old != new:
                item[key] = new
                changed.append(f"{key} geändert")
        if not changed:
            return
        display_name = self.display_name_var.get().strip() or "Admin"
        append_metadata_history(item, display_name, "Metadaten geändert", "; ".join(changed))
        api_ok, api_msg = self.save_item_to_api(item)
        if not api_ok and not auto:
            messagebox.showwarning("MySQL nicht aktualisiert", api_msg)
        self.save_item_json_if_present(item)
        self.remember_document_type(str(item.get("document_type", "")))
        if item.get("upload_id"):
            self.update_admin_document_points_display(str(item.get("upload_id")))
        if hasattr(self, "admin_json_text"):
            self.admin_json_text.configure(state="normal")
            self.admin_json_text.delete("1.0", "end")
            self.admin_json_text.insert("1.0", self.format_metadata_plain({k: v for k, v in item.items() if k != "_metadata_file"}))
            self.admin_json_text.configure(state="disabled")
            self.admin_new_filename_var.set(make_normalized_archive_filename(item, self.admin_new_filename_var.get()))
        add_history(HistoryEntry.now(display_name, "Metadaten geändert", f"{item.get('upload_id')}: {'; '.join(changed[:3])} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        if not auto:
            messagebox.showinfo("Metadaten", "Metadaten wurden gespeichert." if api_ok else "Metadaten wurden lokal gespeichert; MySQL-Aktualisierung fehlgeschlagen.")
