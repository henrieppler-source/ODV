from __future__ import annotations

from pathlib import Path

from .config import APP_DIR


class AdminPolicyManagerMixin:
    def metadata_folder_path(self) -> Path:
        base = self.nextcloud_base_path(show_message=False)
        if base is not None:
            folder_name = self.config_data.get("metadata_folder_name", ".ortschronik_metadaten") or ".ortschronik_metadaten"
            folder_name = str(folder_name).strip().replace("/", "_").replace("\\", "_")
            if not folder_name.startswith("."):
                folder_name = "." + folder_name
            folder = base / folder_name
            if hasattr(self, "metadata_folder_var"):
                self.metadata_folder_var.set(self.normalize_local_path_text(folder))
            self.config_data["metadata_folder"] = self.normalize_local_path_text(folder)
            return folder
        text = self.config_data.get("metadata_folder") or ""
        return Path(text).expanduser() if text else APP_DIR / ".ortschronik_metadaten"

    def is_admin_managed_upload(self, item: dict) -> bool:
        """Admins bearbeiten nur Uploads in den zentral vorgesehenen Arbeitsordnern."""
        base_text = self.base_folder_var.get().strip() if hasattr(self, "base_folder_var") else ""
        if not base_text:
            return True
        base = Path(base_text).expanduser()
        paths_to_check = [item.get("current_path", ""), item.get("target_folder", "")]
        for path_text in paths_to_check:
            if not path_text:
                continue
            try:
                p = Path(path_text).expanduser()
                try:
                    rel_parts = p.relative_to(base).parts
                except ValueError:
                    rel_parts = p.parts
                if any(part in self.admin_work_folder_names for part in rel_parts):
                    return True
            except Exception:
                continue
        return False

    def current_user_id(self) -> int:
        try:
            user = self.current_user or {}
            return int(user.get("id") or user.get("api_id") or self.config_data.get("current_user_id") or 0)
        except Exception:
            return 0

    def is_selected_document_owner(self, item: dict) -> bool:
        uid = self.current_user_id()
        if uid <= 0:
            return False
        try:
            return int(item.get("uploaded_by_user_id") or item.get("user_id") or 0) == uid
        except Exception:
            return False

    def can_edit_admin_item(self, item: dict | None) -> bool:
        if not item:
            return False
        if self.is_current_admin():
            return True
        return self.is_selected_document_owner(item) and str(item.get("status") or "") != "uebernommen"

    def configure_admin_actions_for_role(self) -> None:
        is_admin = self.is_current_admin()
        if hasattr(self, "admin_actions_frame"):
            try:
                self.admin_actions_frame.configure(text="Admin-Aktionen" if is_admin else "Aktionen")
            except Exception:
                pass
        for wname in ("new_status_label", "new_status_combo", "admin_destination_label", "admin_destination_combo", "admin_destination_tree_button", "merge_pdfs_top_button"):
            widget = getattr(self, wname, None)
            if not widget:
                continue
            try:
                if is_admin:
                    widget.grid() if wname != "merge_pdfs_top_button" else widget.pack(side="left", padx=(16, 0))
                else:
                    widget.grid_remove() if wname != "merge_pdfs_top_button" else widget.pack_forget()
            except Exception:
                pass
        if hasattr(self, "admin_rename_button"):
            self.admin_rename_button.configure(text="Datei umbenennen / verschieben" if is_admin else "Dateinamen speichern")
        if hasattr(self, "admin_uploaded_by_combo"):
            try:
                self.admin_uploaded_by_combo.configure(state="readonly" if is_admin else "disabled")
            except Exception:
                pass

    def is_path_in_points_eligible_root(self, item: dict) -> bool:
        """Prüft, ob ein Dokument in einem der fachlich relevanten ODV-Hauptbereiche liegt."""
        text = "\n".join(str(item.get(k, "") or "") for k in ("target_folder", "current_path"))
        norm = text.replace("\\", "/").upper()
        return any(root in norm for root in ("/00_ORTSCHRONIK", "/01_ABLAGE_ORTSCHRONIK", "/06_ARBEIT_DER_ORTSCHRONISTEN", "00_ORTSCHRONIK/", "01_ABLAGE_ORTSCHRONIK/", "06_ARBEIT_DER_ORTSCHRONISTEN/"))

    def should_show_in_admin_documents(self, item: dict) -> bool:
        """Filtert nachträglich aufgenommene vorhandene Dateien für die Admin-Bearbeitungsliste."""
        filename = str(item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "").lower()
        if filename.endswith("_ocr.pdf"):
            return False
        if str(item.get("odv_capture_mode") or "") != "existing_file_metadata":
            return True
        if not self.is_path_in_points_eligible_root(item):
            return False
        captured_by_admin = item.get("odv_captured_by_admin")
        if isinstance(captured_by_admin, str):
            captured_by_admin = captured_by_admin.strip().lower() in {"1", "true", "ja", "yes"}
        if bool(captured_by_admin):
            return False
        return True
