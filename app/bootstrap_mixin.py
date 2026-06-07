from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import tkinter as tk

from .app_logging import app_log, app_log_exception
from .api_client import APIClient
from .config import load_config
from .database import init_db
from .models import PersonMark
from .users import load_users


class BootstrapMixin:
    def bootstrap_window(self) -> None:
        self.title(f"{self.APP_NAME} ({self.APP_SHORT_NAME}) {self.APP_VERSION}")
        self.geometry("1250x920")
        self.withdraw()
        self.show_startup_splash()
        app_log("info", "Anwendung gestartet", version=self.APP_VERSION, app=self.APP_SHORT_NAME)
        self.skip_update_check_once = ("--odv-skip-update-check-once" in sys.argv) or (os.environ.get("ODV_SKIP_UPDATE_CHECK_ONCE") == "1")
        if self.skip_update_check_once:
            app_log("info", "Automatische Updateprüfung für diesen Start unterdrückt", version=self.APP_VERSION)

    def bootstrap_runtime_state(self) -> None:
        self.config_data = load_config()
        init_db()

        self.selected_file: Path | None = None
        self.selected_folder: Path | None = None
        self.upload_ocr_pdf_path: Path | None = None
        self.writable_folders: list[Path] = []
        self.persons: list[PersonMark] = []
        self.admin_uploads: list[dict] = []
        self.file_view_metadata_items: list[dict] = []
        self.file_view_metadata_by_path: dict[str, dict] = {}
        self.file_view_folder_map: dict[str, Path] = {}
        self.file_view_current_path: Path | None = None
        self.file_view_current_metadata: dict | None = None
        self.admin_destination_map: dict[str, Path] = {}
        self.admin_destination_var = None
        self.admin_destination_combo = None
        self.file_view_combo = None
        self.target_combo = None
        self.target_folder_var = None
        self.file_view_merge_pdfs_button = None
        self.file_view_open_ocr_button = None
        self._loading_admin_details = False
        self._last_lock_warning = ""
        self.file_preview_image = None
        self.admin_work_folder_names = set(self.config_data.get("admin_work_folder_names", sorted(self.ADMIN_WORK_FOLDER_NAMES)))
        self.target_folder_map: dict[str, Path] = {}
        self._loading_writable_folders = False
        self._file_view_uploaded_by_user_interaction = False
        self._loading_file_view_metadata = False
        self._admin_uploaded_by_user_interaction = False
        self._pdf_text_searchability_cache: dict[str, tuple[str, bool]] = {}
        self.meta_vars: dict[str, tk.Variable] = {}
        self.file_view_meta_vars: dict[str, tk.Variable] = {}
        self.admin_meta_vars: dict[str, tk.Variable] = {}
        self.admin_detail_vars: dict[str, tk.Variable] = {}
        self.upload_option_comboboxes: dict[str, tk.Widget] = {}
        self.upload_document_type_combo = None
        self.admin_document_type_combo = None
        self.notebook = None
        self.viewer_tab = None
        self.users = load_users(self.config_data.get("display_name", ""))
        self.current_user: dict | None = None
        self.api = APIClient(self.config_data.get("api_url", "https://ortschronik.info/api"))
        self.api_token = str(self.config_data.get("api_token", "") or "")
        self.folder_permissions: dict[str, dict[str, bool]] = {}
        self.place_folder_map: dict[str, str] = {}
        self.openai_metadata_applied_fields: list[str] = []
        self.openai_metadata_suggestions: dict[str, Any] = {}
        self.openai_metadata_source_model = ""

    def bootstrap_tk_variables(self) -> None:
        # Zentrale Tk-Variablen werden einmalig angelegt. Benutzername/Name/Rolle
        # kommen aus der eigenen Benutzerverwaltung; der Nutzer gibt sie nicht
        # mehr auf den Arbeitsseiten ein.
        self.display_name_var = tk.StringVar(value=self.config_data.get("display_name", ""))
        self.username_var = tk.StringVar(value=self.config_data.get("current_username", ""))
        self.email_var = tk.StringVar(value=self.config_data.get("current_email", ""))
        self.role_var = tk.StringVar(value=self.config_data.get("current_role", "Ortschronist"))
        self.role_label_var = tk.StringVar(value=self.role_var.get())
        self.place_var = tk.StringVar(value=self.config_data.get("current_place", ""))
        self.base_folder_var = tk.StringVar(value=self.normalize_local_path_text(self.config_data.get("nextcloud_base_folder", "")))
        self.metadata_folder_var = tk.StringVar(value=self.normalize_local_path_text(self.config_data.get("metadata_folder", "")))

    def bootstrap_startup_flow(self) -> None:
        # Login vor der vollständigen UI-Initialisierung erzwingen.
        # Wenn kein gültiges Token geladen werden kann, wird das Hauptfenster
        # selbst vorübergehend als Anmeldefenster genutzt. Das vermeidet den
        # Tkinter-Fehlerzustand „leeres Hauptfenster ohne sichtbaren Dialog“.
        self.deiconify()
        self.update_idletasks()
        if not self.authenticate_startup_user():
            app_log("warning", "Programmstart ohne erfolgreiche Anmeldung beendet")
            self.destroy()
            return
        self._suspend_notebook_tab_events = True
        self.create_ui()
        self.after(300, self._release_tab_event_suspend)
        self.restore_window_geometry(self, "main_window", "1250x920")
        self.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        self.deiconify()
        if not self.ui_settings().get("main_window", {}).get("geometry"):
            self.after(50, self.maximize_window)
        self.after(150, self._run_startup_background_tasks)
        self.after(150, self.refresh_window_title)
        self.after(1200, lambda: threading.Thread(target=self.ensure_ghostscript_on_startup, daemon=True).start())
        self.after(500, self.show_startup_action_warnings)
        if not self.skip_update_check_once:
            self.after(7600, self.check_app_update_on_startup)
        else:
            app_log("info", "Start-Updateprüfung übersprungen, weil ODV gerade aus einem Update gestartet wurde")

    def _run_startup_background_tasks(self) -> None:
        """Führt potenziell längere Startaufgaben aus, nachdem das Fenster sichtbar ist."""
        try:
            self.refresh_history()
        except Exception as exc:
            app_log_exception("Initiale Historie konnte nicht geladen werden", exc)
        try:
            self.load_folders_from_config()
        except Exception as exc:
            app_log_exception("Startordner konnten nicht geladen werden", exc)

    def _release_tab_event_suspend(self) -> None:
        self._suspend_notebook_tab_events = False
        self.after_idle(self.update_tab_labels)
