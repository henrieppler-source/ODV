from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .app_logging import app_log_exception


class AdminListManagerMixin:
    def refresh_admin_uploads(self, show_message: bool = True) -> None:
        """Lädt im API-/Produktivmodus ausschließlich aktive MySQL/API-Datensätze.

        Lokale JSON-Dateien bleiben Sicherung, werden hier aber nicht mehr als
        aktive Bearbeitungsliste eingemischt. Verwaiste Sicherungen werden über
        Admin > Lokale Sicherungsdateien prüfen/bereinigen geprüft.
        """
        self.configure_admin_actions_for_role()

        for row in self.admin_tree.get_children():
            self.admin_tree.delete(row)

        wanted_status = self.admin_status_var.get() if hasattr(self, "admin_status_var") else "alle"
        visible: list[dict] = []
        self.admin_uploads = []

        if not self.api_token:
            if show_message:
                messagebox.showwarning("API", "Keine API-Anmeldung vorhanden. Dateien bearbeiten zeigt im Produktivmodus nur MySQL/API-Datensätze.")
            return

        try:
            only_own = not self.is_current_admin()
            response = self.api.list_documents(self.api_token, status=wanted_status if wanted_status != "alle" else None, only_own=only_own)
            self.admin_uploads = [self.api_document_to_item(doc) for doc in response.get("documents", [])]
            self.refresh_document_type_options_from_documents(self.admin_uploads)
            if not self.is_current_admin():
                self.admin_uploads = [it for it in self.admin_uploads if str(it.get("status") or "") != "uebernommen" and self.is_selected_document_owner(it)]
            for _item in self.admin_uploads:
                self.normalize_admin_item_path_for_current_pc(_item)
                _p = self.resolve_document_local_path(_item)
                if _p and not _item.get("document_type"):
                    _item["document_type"] = detect_document_type(_p)
            visible = [it for it in self.admin_uploads if self.should_show_in_admin_documents(it)]
        except ApiError as exc:
            app_log_exception("Admin-Dokumentliste konnte nicht aus MySQL/API geladen werden", exc)
            if show_message:
                messagebox.showwarning(
                    "API nicht erreichbar",
                    "Dateien bearbeiten zeigt im Produktivmodus nur MySQL/API-Datensätze.\n"
                    "Lokale JSON-Sicherungen werden hier nicht automatisch angezeigt.\n\n"
                    f"{exc}",
                )
            return

        for item in visible:
            upload_id = str(item.get("upload_id", ""))
            if not upload_id:
                continue
            self.admin_tree.insert(
                "",
                "end",
                iid=upload_id,
                values=(
                    upload_id,
                    item.get("status", "hochgeladen"),
                    item.get("current_filename") or item.get("stored_filename") or item.get("original_filename", ""),
                    item.get("uploaded_by") or item.get("uploaded_by_name", ""),
                    item.get("uploaded_at", ""),
                    item.get("document_type", ""),
                ),
            )
        if show_message:
            messagebox.showinfo("Dateien bearbeiten", f"{len(visible)} Uploads aus MySQL/API angezeigt.")

    def selected_admin_upload(self) -> dict | None:
        selection = self.admin_tree.selection()
        if not selection:
            return None
        upload_id = selection[0]
        for item in self.admin_uploads:
            if item.get("upload_id") == upload_id:
                return item
        return None

    def refresh_admin_destination_choices(self) -> None:
        if not hasattr(self, "admin_destination_combo"):
            return
        # Zielordner sind die bereits ermittelten, lokal beschreibbaren Nextcloud-Ordner.
        # Wichtig: Hier NICHT erneut load_writable_folders() aufrufen, sonst entsteht beim Start
        # eine Rekursion: load_writable_folders -> refresh_admin_destination_choices -> load_writable_folders.
        base = Path(self.base_folder_var.get().strip()).expanduser()
        folders = list(getattr(self, "writable_folders", []) or [])
        self.admin_destination_map = {self.display_path_for_folder(path, base): path for path in folders}
        values = sorted(self.admin_destination_map.keys(), key=str.lower)
        self.admin_destination_combo["values"] = values
        if values and self.admin_destination_var.get() not in values:
            self.admin_destination_var.set(values[0])
        elif not values:
            self.admin_destination_var.set("")

    def choose_admin_destination(self) -> None:
        self.refresh_admin_destination_choices()
        selected = self.open_folder_tree_dialog("Datei ablegen in", self.writable_folders, self.admin_destination_var.get())
        if selected:
            self.select_combobox_path(self.admin_destination_var, self.admin_destination_combo, self.admin_destination_map, selected)

    def status_archive_target(self, status: str) -> Path | None:
        """Zielordner für Archivstatus unter 01_ABLAGE_ORTSCHRONIK."""
        status = self.normalize_document_status(status)
        folder_name = {"archiviert": "ARCHIVIERT"}.get(status)
        if not folder_name:
            return None
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        return base / "01_ABLAGE_ORTSCHRONIK" / "_ARCHIV" / folder_name

    def is_path_under_named_folder(self, path: Path, folder_name: str) -> bool:
        token = self.normalize_folder_token(folder_name)
        try:
            return any(self.normalize_folder_token(part) == token for part in path.parts)
        except Exception:
            return False

