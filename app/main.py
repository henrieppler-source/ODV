from __future__ import annotations

import shutil
import json
import re
import unicodedata
import os
import platform
import subprocess
import sys
import atexit
import uuid
import socket
import getpass
import threading
import ftplib
import posixpath
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TK_BASE_CLASS = TkinterDnD.Tk
except Exception:  # Drag & Drop bleibt optional; ohne Bibliothek läuft ODV normal weiter.
    DND_FILES = None
    TkinterDnD = None
    TK_BASE_CLASS = tk.Tk

from .config import APP_DIR, load_config, save_config
from .database import init_db, add_history
from .users import (
    load_users,
    find_user_by_username,
    role_allows_admin,
)
from .file_service import (
    is_writable_folder,
    is_image_file,
    make_upload_id,
    safe_filename,
    make_normalized_archive_filename,
    unique_path_with_counter,
    copy_with_metadata,
    detect_document_type,
    load_metadata_files,
    save_metadata_file,
    append_metadata_history,
)
from .models import UploadMetadata, HistoryEntry, PersonMark
from .person_tagger import PersonTagger
from .api_client import APIClient, ApiError
from .openai_client import OpenAIClient, OpenAIError
from .secure_store import SecureStoreError, protect_text, unprotect_text
from .app_logging import app_log, app_log_exception
from .admin_operations import AdminOperationsMixin
from .config_folders import ConfigFoldersMixin
from .help_docs import HelpDocsMixin
from .history_manager import HistoryManagerMixin
from .mail_manager import MailManagerMixin
from .masterdata_manager import MasterdataManagerMixin
from .metadata_helpers import MetadataHelpersMixin
from .points_manager import PointsManagerMixin
from .points_year_manager import PointsYearManagerMixin
from .single_instance import acquire_single_instance_lock, release_single_instance_lock, resource_path
from .system_status import SystemStatusMixin
from .ui_state import UiStateMixin
from .update_manager import AppUpdateMixin
from .user_admin import UserAdminMixin
from .upload_tab import UploadTabMixin
from PIL import Image, ImageTk, ImageDraw, ImageFont

APP_NAME = "Ortschronisten-Datei-Verwaltung"
APP_SHORT_NAME = "ODV"
APP_VERSION = "v112"

class OrtschronikUploader(HelpDocsMixin, HistoryManagerMixin, UiStateMixin, SystemStatusMixin, AppUpdateMixin, AdminOperationsMixin, PointsYearManagerMixin, PointsManagerMixin, MailManagerMixin, UserAdminMixin, MasterdataManagerMixin, ConfigFoldersMixin, MetadataHelpersMixin, UploadTabMixin, TK_BASE_CLASS):
    APP_SHORT_NAME = APP_SHORT_NAME
    APP_VERSION = APP_VERSION
    ADMIN_WORK_FOLDER_NAMES = {"01_ABLAGE_ORTSCHRONIK", "06_ARBEIT_DER_ORTSCHRONISTEN"}
    FOLDER_GROUPS = [
        ("00_ORTSCHRONIK", "00_ORTSCHRONIK"),
        ("01_ABLAGE_ORTSCHRONIK", "01_ABLAGE_ORTSCHRONIK"),
        ("02_AUSTAUSCH", "02_AUSTAUSCH"),
        ("03_INFORMATION", "03_INFORMATION"),
        ("05_ORGA_CHRONISTEN", "05_ORGA_CHRONISTEN"),
        ("06_UNSERE_ARBEITEN", "06_UNSERE_ARBEITEN"),
        ("OWN_PLACE_FOLDER", "Eigener Ortsordner"),
        ("OTHER_PLACE_FOLDERS", "Andere Ortsordner"),
    ]


    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION}")
        self.geometry("1250x920")
        self.withdraw()
        self.show_startup_splash()
        app_log("info", "Anwendung gestartet", version=APP_VERSION, app=APP_SHORT_NAME)
        self.skip_update_check_once = ("--odv-skip-update-check-once" in sys.argv) or (os.environ.get("ODV_SKIP_UPDATE_CHECK_ONCE") == "1")
        if self.skip_update_check_once:
            app_log("info", "Automatische Updateprüfung für diesen Start unterdrückt", version=APP_VERSION)
        self.config_data = load_config()
        init_db()

        self.selected_file: Path | None = None
        self.selected_folder: Path | None = None
        self.writable_folders: list[Path] = []
        self.persons: list[PersonMark] = []
        self.admin_uploads: list[dict] = []
        self.file_view_metadata_items: list[dict] = []
        self.file_view_metadata_by_path: dict[str, dict] = {}
        self.file_view_folder_map: dict[str, Path] = {}
        self.file_view_current_path: Path | None = None
        self.file_view_current_metadata: dict | None = None
        self.file_preview_image = None
        self.admin_work_folder_names = set(self.config_data.get("admin_work_folder_names", sorted(self.ADMIN_WORK_FOLDER_NAMES)))
        self.target_folder_map: dict[str, Path] = {}
        self.users = load_users(self.config_data.get("display_name", ""))
        self.current_user: dict | None = None
        self.api = APIClient(self.config_data.get("api_url", "https://ortschronik.info/api"))
        self.api_token = str(self.config_data.get("api_token", "") or "")
        self.folder_permissions: dict[str, dict[str, bool]] = {}
        self.place_folder_map: dict[str, str] = {}
        self.openai_metadata_applied_fields: list[str] = []

        # Zentrale Tk-Variablen werden einmalig angelegt. Benutzername/Name/Rolle
        # kommen aus der eigenen Benutzerverwaltung; der Nutzer gibt sie nicht
        # mehr auf den Arbeitsseiten ein.
        self.display_name_var = tk.StringVar(value=self.config_data.get("display_name", ""))
        self.username_var = tk.StringVar(value=self.config_data.get("current_username", ""))
        self.role_var = tk.StringVar(value=self.config_data.get("current_role", "Ortschronist"))
        self.role_label_var = tk.StringVar(value=self.role_var.get())
        self.place_var = tk.StringVar(value=self.config_data.get("current_place", ""))
        self.base_folder_var = tk.StringVar(value=self.normalize_local_path_text(self.config_data.get("nextcloud_base_folder", "")))
        self.metadata_folder_var = tk.StringVar(value=self.normalize_local_path_text(self.config_data.get("metadata_folder", "")))

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
        self.create_ui()
        self.restore_window_geometry(self, "main_window", "1250x920")
        self.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        self.deiconify()
        if not self.ui_settings().get("main_window", {}).get("geometry"):
            self.after(50, self.maximize_window)
        self.refresh_history()
        self.load_folders_from_config()
        self.refresh_window_title()
        self.after(500, self.show_startup_action_warnings)
        if not self.skip_update_check_once:
            self.after(7600, self.check_app_update_on_startup)
        else:
            app_log("info", "Start-Updateprüfung übersprungen, weil ODV gerade aus einem Update gestartet wurde")

    def show_startup_splash(self) -> None:
        """Zeigt beim Programmstart kurz ein Startfenster mit Logo und Anwendungsname."""
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg="white")
        splash.attributes("-topmost", True)

        frame = tk.Frame(splash, bg="white", bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        logo_path = resource_path("app/assets/odv_logo.png")
        logo_photo = None
        if logo_path.exists():
            try:
                img = Image.open(logo_path).convert("RGBA")
                img.thumbnail((170, 170), Image.LANCZOS)
                logo_photo = ImageTk.PhotoImage(img)
                logo_label = tk.Label(frame, image=logo_photo, bg="white")
                logo_label.image = logo_photo
                logo_label.pack(pady=(22, 8))
            except Exception as exc:
                app_log_exception("Splash-Logo konnte nicht geladen werden", exc)

        tk.Label(
            frame,
            text=APP_NAME,
            bg="white",
            fg="#1f1f1f",
            font=("Segoe UI", 17, "bold"),
        ).pack(padx=36, pady=(6, 0))
        tk.Label(
            frame,
            text=f"{APP_SHORT_NAME} · {APP_VERSION}",
            bg="white",
            fg="#555555",
            font=("Segoe UI", 11),
        ).pack(padx=36, pady=(4, 20))
        tk.Label(
            frame,
            text="Dateien · Metadaten · Ortschronik",
            bg="white",
            fg="#777777",
            font=("Segoe UI", 9),
        ).pack(padx=36, pady=(0, 24))

        splash.update_idletasks()
        width = 580
        height = 390
        x = max(0, (splash.winfo_screenwidth() - width) // 2)
        y = max(0, (splash.winfo_screenheight() - height) // 2)
        splash.geometry(f"{width}x{height}+{x}+{y}")
        splash.update()
        self.after(5200, splash.destroy)
        self.wait_window(splash)

    def create_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.create_menu()
        self.create_styles()

        notebook = ttk.Notebook(self)
        self.notebook = notebook
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.create_status_bar()

        self.history_tab = ttk.Frame(notebook, padding=10, style="Dashboard.TFrame")
        self.upload_tab_container = ttk.Frame(notebook, style="Upload.TFrame")
        self.upload_tab = self.make_scrollable_tab(self.upload_tab_container)
        self.viewer_tab = ttk.Frame(notebook, padding=10, style="Viewer.TFrame")
        self.admin_tab = ttk.Frame(notebook, padding=10, style="Admin.TFrame")
        self.admin_tab_visible = True

        notebook.add(self.history_tab, text="Dashboard")
        notebook.add(self.upload_tab_container, text="Dateien hochladen")
        notebook.add(self.viewer_tab, text="Dateien anzeigen")
        notebook.add(self.admin_tab, text="Dateien bearbeiten")
        notebook.bind("<<NotebookTabChanged>>", self.on_notebook_tab_changed)

        self.create_history_tab()
        self.create_upload_tab()
        self.create_file_view_tab()
        self.create_admin_tab()
        self.ensure_standard_metadata_folder()
        self.apply_selected_user()
        self.update_tab_labels()
        self.update_connection_status()
        self.bind_global_mousewheel()


    def normalize_local_path_text(self, value: str | Path) -> str:
        """Lokale Pfade einheitlich im Betriebssystemformat darstellen."""
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return os.path.normpath(text)
        except Exception:
            return text.replace("/", "\\") if os.name == "nt" else text.replace("\\", "/")

    def known_top_folder_tokens(self) -> set[str]:
        tokens = {self.normalize_folder_token(key) for key, _label in self.FOLDER_GROUPS if not key.endswith("_FOLDER")}
        tokens.update({self.normalize_folder_token(v) for v in self.place_folder_map.values() if v})
        tokens.update({self.normalize_folder_token(v) for v in self.admin_work_folder_names if v})
        return {t for t in tokens if t}

    def document_candidate_suffixes(self, item: dict | None) -> list[str]:
        """Mögliche Dateiendungen aus DB-Feldern und Dokumenttyp ableiten.

        Ältere Datensätze enthalten teilweise Dateinamen ohne echte Endung oder mit
        ersetztem Punkt, z. B. ``datei_jpg`` statt ``datei.jpg``. Diese Liste hilft
        der Dateiauflösung, solche Fälle trotzdem im Nextcloud-Ordner zu finden.
        """
        suffixes: list[str] = []
        if item:
            for key in ("current_filename", "stored_filename", "original_filename", "current_path", "target_folder"):
                value = str(item.get(key) or "").strip()
                if not value:
                    continue
                suffix = Path(value).suffix.lower()
                if suffix and suffix not in suffixes:
                    suffixes.append(suffix)
            doc_type = str(item.get("document_type") or item.get("type") or "").lower()
            if "bild" in doc_type or "foto" in doc_type:
                defaults = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".gif"]
            elif "pdf" in doc_type:
                defaults = [".pdf"]
            elif "video" in doc_type:
                defaults = [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v"]
            elif "audio" in doc_type:
                defaults = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]
            elif "tabelle" in doc_type or "csv" in doc_type or "excel" in doc_type:
                defaults = [".csv", ".xlsx", ".xls", ".ods"]
            elif "text" in doc_type or "word" in doc_type:
                defaults = [".txt", ".docx", ".doc", ".rtf", ".odt", ".md"]
            else:
                defaults = []
            for suffix in defaults:
                if suffix not in suffixes:
                    suffixes.append(suffix)
        return suffixes

    def document_candidate_filenames(self, item: dict | None, preferred_name: str | None = None) -> list[str]:
        """Robuste Namensvarianten für vorhandene lokale Dateien bilden.

        Behandelt u. a. Altdaten wie ``name_jpg`` / ``name_jpg.jpg`` und fehlende
        Dateiendungen. Die Reihenfolge ist bewusst: zuerst DB-Wert, dann Varianten.
        """
        raw_names: list[str] = []
        if preferred_name:
            raw_names.append(str(preferred_name))
        if item:
            for key in ("current_filename", "stored_filename", "original_filename"):
                value = str(item.get(key) or "").strip()
                if value:
                    raw_names.append(Path(value).name)
            for key in ("current_path",):
                value = str(item.get(key) or "").strip()
                if value:
                    raw_names.append(Path(value).name)
        suffixes = self.document_candidate_suffixes(item)
        result: list[str] = []

        def add(name: str) -> None:
            name = (name or "").strip()
            if name and name not in result:
                result.append(name)

        for name in raw_names:
            add(name)
            path_name = Path(name)
            suffix = path_name.suffix.lower()
            if not suffix:
                for ext in suffixes:
                    add(name + ext)
                    token = ext.lstrip(".").lower()
                    lower = name.lower()
                    for sep in ("_", "-", " "):
                        tail = sep + token
                        if lower.endswith(tail):
                            add(name[: -len(tail)] + ext)
            else:
                token = suffix.lstrip(".").lower()
                lower_stem = path_name.stem.lower()
                for sep in ("_", "-", " "):
                    tail = sep + token
                    if lower_stem.endswith(tail):
                        add(path_name.stem[: -len(tail)] + suffix)
        return result

    def find_candidate_file_in_folder(self, folder: Path, item: dict | None, preferred_name: str | None = None) -> Path | None:
        if not folder.exists() or not folder.is_dir():
            return None
        for name in self.document_candidate_filenames(item, preferred_name):
            candidate = folder / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def resolve_document_local_path(self, item: dict | None) -> Path | None:
        """Findet die lokale Datei robust auch bei Altdaten/Pfaddifferenzen.

        MySQL speichert ggf. den lokalen Pfad des hochladenden Rechners. Auf einem
        anderen PC wird daraus über das eigene Nextcloud-Stammverzeichnis ein
        passender lokaler Pfad gebaut. Zusätzlich werden fehlende/verdoppelte
        Dateiendungen tolerant behandelt, z. B. ``datei_jpg`` -> ``datei_jpg.jpg``
        oder ``datei.jpg``.
        """
        if not item:
            return None

        for text in [item.get("current_path")]:
            if not text:
                continue
            try:
                p = Path(str(text))
                if p.exists() and p.is_file():
                    return p
                # Wenn der gespeicherte Dateiname keine echte Endung enthält oder
                # der Punkt zu _ wurde, im gleichen Ordner Varianten suchen.
                folder = p.parent
                found = self.find_candidate_file_in_folder(folder, item, p.name)
                if found:
                    return found
            except Exception:
                pass

        # target_folder ist normalerweise ein Ordner, kann in Altdaten aber auch ein Pfad sein.
        for text in [item.get("target_folder")]:
            if not text:
                continue
            try:
                p = Path(str(text))
                if p.exists() and p.is_file():
                    return p
                folder = p if p.exists() and p.is_dir() else p.parent
                found = self.find_candidate_file_in_folder(folder, item)
                if found:
                    return found
            except Exception:
                pass

        base_text = self.base_folder_var.get().strip() if hasattr(self, "base_folder_var") else ""
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        if not base.exists():
            return None

        tokens = self.known_top_folder_tokens()
        for text in [item.get("current_path"), item.get("target_folder")]:
            if not text:
                continue
            parts = Path(str(text)).parts
            for i, part in enumerate(parts):
                if self.normalize_folder_token(part) in tokens:
                    rel_parts = parts[i:]
                    candidate = base.joinpath(*rel_parts)
                    if candidate.exists() and candidate.is_file():
                        return candidate
                    # gespeicherter Pfad zeigt evtl. auf nicht existierende Datei:
                    # dann im rekonstruierten Elternordner nach Varianten suchen.
                    folder = candidate if candidate.exists() and candidate.is_dir() else candidate.parent
                    found = self.find_candidate_file_in_folder(folder, item, candidate.name)
                    if found:
                        return found

        # letzte Rückfallebene: unterhalb des Nextcloud-Stammordners nach Varianten suchen
        for name in self.document_candidate_filenames(item):
            try:
                matches = list(base.rglob(name))
                if matches:
                    return matches[0]
            except Exception:
                pass
        return None

    def normalize_admin_item_path_for_current_pc(self, item: dict) -> None:
        path = self.resolve_document_local_path(item)
        if path:
            item["current_path"] = str(path)
            item["target_folder"] = str(path.parent)

    def create_status_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 2))
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.api_status_var = tk.StringVar(value="API: wird geprüft …")
        self.nextcloud_status_var = tk.StringVar(value="Nextcloud: nicht geprüft")
        ttk.Label(bar, textvariable=self.api_status_var).grid(row=0, column=0, sticky="w", padx=(0, 20))
        ttk.Label(bar, textvariable=self.nextcloud_status_var).grid(row=0, column=1, sticky="w")

    def update_connection_status(self) -> None:
        if not hasattr(self, "api_status_var"):
            return
        try:
            status = self.api.status()
            api_version = str(status.get("api_version") or status.get("version") or "?")
            version_note = f"API: verbunden ({api_version})"
            if api_version not in ("?", APP_VERSION):
                version_note += f" – Achtung: App {APP_VERSION}"
            maintenance = status.get("maintenance") or {}
            if maintenance.get("active"):
                version_note += " – Wartungsmodus aktiv"
            elif maintenance.get("scheduled"):
                version_note += " – Wartung geplant"
            self.api_status_var.set(version_note)
            self.report_current_device_version()
        except Exception as exc:
            self.api_status_var.set("API: nicht erreichbar")
            app_log_exception("API-Statusprüfung fehlgeschlagen", exc)
        try:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            if base and base.exists() and base.is_dir():
                self.nextcloud_status_var.set(f"Nextcloud: gefunden ({base})")
            else:
                self.nextcloud_status_var.set("Nextcloud: Stammverzeichnis nicht gesetzt/gefunden")
        except Exception as exc:
            self.nextcloud_status_var.set("Nextcloud: Fehler bei Prüfung")
            app_log_exception("Nextcloud-Stammverzeichnis konnte nicht geprüft werden", exc)

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Stammdaten...", command=self.open_masterdata_dialog)
        file_menu.add_command(label="Nextcloud-Zielordner neu prüfen", command=self.load_writable_folders)
        file_menu.add_separator()
        file_menu.add_command(label="Benutzer wechseln...", command=self.logout_and_login)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)

        # Admin: echte Verwaltung / Betrieb
        if self.current_role() == "Superadmin":
            admin_menu = tk.Menu(menubar, tearoff=False)
            admin_menu.add_command(label="Admin-Einstellungen...", command=self.open_admin_settings_dialog)

            user_admin_menu = tk.Menu(admin_menu, tearoff=False)
            user_admin_menu.add_command(label="Benutzer verwalten...", command=self.open_user_management_dialog)
            admin_menu.add_cascade(label="Benutzerverwaltung", menu=user_admin_menu)

            masterdata_menu = tk.Menu(admin_menu, tearoff=False)
            masterdata_menu.add_command(label="Ortsordner-Stammdaten...", command=self.open_place_folder_dialog)
            masterdata_menu.add_command(label="Archiv/Sammlung-Stammdaten...", command=self.open_archive_collection_dialog)
            admin_menu.add_cascade(label="Stammdaten", menu=masterdata_menu)

            file_admin_menu = tk.Menu(admin_menu, tearoff=False)
            file_admin_menu.add_command(label="Vorhandene Dateien einlesen...", command=self.open_import_existing_files_dialog)
            file_admin_menu.add_command(label="Lokale Sicherungsdateien prüfen/bereinigen...", command=self.open_local_backup_cleanup_dialog)
            admin_menu.add_cascade(label="Dateien", menu=file_admin_menu)

            database_menu = tk.Menu(admin_menu, tearoff=False)
            database_menu.add_command(label="Wartungsmodus / Datenbanksperre...", command=self.open_maintenance_dialog)
            database_menu.add_command(label="Datenbankmigrationen prüfen/ausführen...", command=self.open_database_migrations_dialog)
            database_menu.add_command(label="Datenbank zurücksetzen...", command=self.open_database_reset_dialog)
            database_menu.add_separator()
            database_menu.add_command(label="Datenbank sichern...", command=self.open_database_backup_dialog)
            database_menu.add_command(label="Backup zurücksichern...", command=self.open_database_restore_dialog)
            admin_menu.add_cascade(label="Datenbank", menu=database_menu)

            server_menu = tk.Menu(admin_menu, tearoff=False)
            server_menu.add_command(label="routes.php sichern/hochladen...", command=self.open_routes_deploy_dialog)
            admin_menu.add_cascade(label="Server", menu=server_menu)

            update_menu = tk.Menu(admin_menu, tearoff=False)
            update_menu.add_command(label="ODV-Updatefreigabe verwalten...", command=self.open_app_update_admin_dialog)
            admin_menu.add_cascade(label="Updates", menu=update_menu)
            menubar.add_cascade(label="Admin", menu=admin_menu)

        # Punkte: alles rund um automatische und manuelle Punkte
        points_menu = tk.Menu(menubar, tearoff=False)
        points_menu.add_command(label="Mein Punktestand...", command=self.open_my_points_dialog)
        if self.is_current_admin():
            points_menu.add_separator()
            points_menu.add_command(label="Punkteübersicht...", command=self.open_points_summary_dialog)
            points_menu.add_command(label="Manuelle Sonderpunkte vergeben...", command=self.open_manual_special_points_dialog)
            points_menu.add_command(label="Übersicht manuelle Sonderpunkte...", command=self.open_manual_special_points_overview_dialog)
            points_menu.add_command(label="Sonderpunkte zum ausgewählten Dokument...", command=self.open_manual_points_dialog)
            if self.current_role() == "Superadmin":
                points_menu.add_separator()
                points_menu.add_command(label="Punkteregeln verwalten...", command=self.open_point_rules_dialog)
                points_menu.add_command(label="Punkte für vorhandene Dokumente neu berechnen...", command=self.recalculate_points_for_visible_admin_uploads)
                points_menu.add_command(label="Punkte-Einstellungen...", command=self.open_points_settings_dialog)
        menubar.add_cascade(label="Punkte", menu=points_menu)

        if self.is_current_admin():
            mail_menu = tk.Menu(menubar, tearoff=False)
            mail_menu.add_command(label="Rundmail erstellen...", command=self.open_information_mail_dialog)
            mail_menu.add_command(label="Verteiler verwalten...", command=self.open_mail_group_management_dialog)
            mail_menu.add_separator()
            mail_menu.add_command(label="Versandhistorie...", command=self.open_mail_history_dialog)
            menubar.add_cascade(label="Mail", menu=mail_menu)

        if self.is_current_admin():
            overview_menu = tk.Menu(menubar, tearoff=False)
            overview_menu.add_command(label="Dokumentzugriffe...", command=self.open_document_access_log_dialog)
            overview_menu.add_command(label="Sitzungen und Geräte...", command=self.open_sessions_devices_dialog)
            overview_menu.add_command(label="Backup-Status...", command=self.open_backup_status_dialog)
            menubar.add_cascade(label="Übersichten", menu=overview_menu)

        # Der frühere Menüpunkt "Ansicht" wurde entfernt.
        # Aktualisierungen erfolgen automatisch beim Reiterwechsel bzw. durch die jeweiligen Bedienaktionen;
        # Spaltenbreiten werden automatisch gespeichert.

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Handbuch", command=lambda: self.open_markdown_handbook("Handbuch.md", "ODV-Handbuch"))
        if self.is_current_admin():
            help_menu.add_command(label="Admin-Handbuch", command=lambda: self.open_markdown_handbook("Admin-Handbuch.md", "ODV-Admin-Handbuch"))
        if self.current_role() == "Superadmin":
            help_menu.add_command(label="Versionshistorie", command=lambda: self.open_markdown_handbook("README.md", "ODV-Versionshistorie"))
        help_menu.add_separator()
        help_menu.add_command(label="Info", command=lambda: messagebox.showinfo(APP_NAME, f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION}\nNextcloud, API/MySQL\n(c) Henri Eppler, 2026"))
        help_menu.add_command(label="Systemstatus...", command=self.open_system_status_dialog)
        help_menu.add_command(label="Nach ODV-Update suchen...", command=lambda: self.check_app_update(interactive=True))
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.config(menu=menubar)

    def api_role_to_local(self, role: str) -> str:
        mapping = {"ortschronist": "Ortschronist", "admin": "Admin", "superadmin": "Superadmin"}
        return mapping.get(str(role).strip().lower(), str(role).strip() or "Ortschronist")

    def local_role_to_api(self, role: str) -> str:
        mapping = {"Ortschronist": "ortschronist", "Admin": "admin", "Superadmin": "superadmin"}
        return mapping.get(str(role).strip(), "ortschronist")

    def normalize_folder_token(self, value: str) -> str:
        """Normiert Orts-/Ordnernamen für einfache Rechtefilter, z. B. Römhild -> roemhild."""
        text = str(value or "").strip().lower()
        replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return "".join(ch for ch in text if ch.isalnum())

    def top_level_folder_name(self, folder: Path, base: Path) -> str:
        try:
            rel = folder.relative_to(base)
            if str(rel) == ".":
                return "."
            return rel.parts[0] if rel.parts else "."
        except ValueError:
            return folder.name

    def is_odv_update_path(self, path: Path) -> bool:
        """Technischen Nextcloud-Updateordner aus normalen Ablage-/Auswahlbäumen ausblenden."""
        return any(str(part).strip().upper() == "ODV_UPDATE" for part in path.parts)

    def is_hidden_system_path(self, path: Path) -> bool:
        """Blendet technische Systemdateien aus normalen ODV-Bäumen aus."""
        name = str(path.name or "").strip()
        lower = name.lower()
        # Technische System-/Syncdateien konsequent aus normalen ODV-Bäumen ausblenden.
        if lower in {"desktop.ini", "thumbs.db", ".ds_store", ".nextcloudsync.log"}:
            return True
        if name.upper() == "_ARCHIV" or lower in {"archiv", "abgelehnt", "geloescht", "gelöscht"}:
            return True
        if lower.endswith(".tmp") or lower.startswith("~$"):
            return True
        if lower.startswith(".sync_") and (lower.endswith(".db") or lower.endswith(".db-shm") or lower.endswith(".db-wal")):
            return True
        if name.startswith(".ortschronik_"):
            return True
        if self.is_odv_update_path(path):
            return True
        return False

    def normalize_search_text(self, value: str) -> str:
        """Normiert Suchbegriffe/Dateinamen: klein, ohne Umlaute/Sonderzeichen."""
        return self.normalize_folder_token(value)

    def default_folder_permissions(self) -> dict[str, dict[str, bool]]:
        role = self.current_role()
        if role in ("Admin", "Superadmin"):
            return {key: {"read": True, "write": True} for key, _ in self.FOLDER_GROUPS}
        defaults = {
            "00_ORTSCHRONIK": {"read": True, "write": False},
            "01_ABLAGE_ORTSCHRONIK": {"read": True, "write": True},
            "02_AUSTAUSCH": {"read": True, "write": True},
            "03_INFORMATION": {"read": True, "write": False},
            "05_ORGA_CHRONISTEN": {"read": False, "write": False},
            "06_UNSERE_ARBEITEN": {"read": True, "write": True},
            "OWN_PLACE_FOLDER": {"read": True, "write": True},
            "OTHER_PLACE_FOLDERS": {"read": False, "write": False},
        }
        return defaults

    def load_current_folder_permissions(self) -> None:
        """Lädt Rechte und Ortsordner-Stammdaten aus der API.

        Fallback: sinnvolle Standardrechte, damit die App auch weiterarbeitet,
        wenn die neue Rechte-API noch nicht installiert ist.
        """
        self.folder_permissions = self.default_folder_permissions()
        if self.api_token:
            try:
                response = self.api.get_folder_permissions(self.api_token)
                perms = response.get("permissions", [])
                loaded: dict[str, dict[str, bool]] = {}
                for row in perms:
                    key = str(row.get("folder_group", "")).strip()
                    if not key:
                        continue
                    loaded[key] = {
                        "read": bool(int(row.get("can_read", 0) or 0)),
                        "write": bool(int(row.get("can_write", 0) or 0)),
                    }
                if loaded:
                    self.folder_permissions.update(loaded)
            except Exception as exc:
                app_log_exception("Ordnerrechte konnten nicht aus API geladen werden", exc)
            try:
                response = self.api.list_place_folders(self.api_token)
                self.place_folder_map = {
                    self.normalize_folder_token(str(row.get("place", ""))): str(row.get("folder_name", "")).strip()
                    for row in response.get("places", []) if row.get("place") and row.get("folder_name")
                }
            except Exception as exc:
                app_log_exception("Ortsordner-Stammdaten konnten nicht aus API geladen werden", exc)
                self.place_folder_map = dict(self.config_data.get("place_folder_map", {}) or {})
        else:
            self.place_folder_map = dict(self.config_data.get("place_folder_map", {}) or {})

    def folder_permission_group(self, folder: Path, base: Path) -> str | None:
        """Ermittelt die fachliche Ordnergruppe auch dann, wenn die ODV-Struktur
        nicht direkt im Nextcloud-Stamm liegt, sondern z. B. unter
        Ortschronisten_Gemeinsam\00_ORTSCHRONIK.
        """
        try:
            rel_parts = folder.relative_to(base).parts
        except ValueError:
            rel_parts = folder.parts
        if not rel_parts:
            rel_parts = (folder.name,)

        fixed = [
            "00_ORTSCHRONIK",
            "01_ABLAGE_ORTSCHRONIK",
            "02_AUSTAUSCH",
            "03_INFORMATION",
            "05_ORGA_CHRONISTEN",
            "06_UNSERE_ARBEITEN",
        ]
        normalized_parts = [self.normalize_folder_token(part) for part in rel_parts]
        for name in fixed:
            token = self.normalize_folder_token(name)
            if token in normalized_parts:
                return name

        place_norm = self.normalize_folder_token(self.place_var.get())
        own_folder = self.place_folder_map.get(place_norm, "")
        own_token = self.normalize_folder_token(own_folder)
        if own_token and own_token in normalized_parts:
            return "OWN_PLACE_FOLDER"
        if place_norm and any(place_norm in part for part in normalized_parts):
            return "OWN_PLACE_FOLDER"

        known_place_folders = {self.normalize_folder_token(v) for v in self.place_folder_map.values() if v}
        for part, norm in zip(rel_parts, normalized_parts):
            if norm in known_place_folders:
                return "OTHER_PLACE_FOLDERS"
            if len(str(part)) >= 3 and str(part)[:2].isdigit() and "_" in str(part):
                return "OTHER_PLACE_FOLDERS"
        return None

    def folder_group_allowed(self, group: str | None, mode: str = "write") -> bool:
        if not group:
            return False
        perms = self.folder_permissions or self.default_folder_permissions()
        row = perms.get(group)
        if not row:
            return False
        return bool(row.get("write" if mode == "write" else "read", False))

    def default_upload_target(self) -> str | None:
        """Standardmäßig 01_ABLAGE_ORTSCHRONIK auswählen, falls erlaubt."""
        preferred = "01_ABLAGE_ORTSCHRONIK"
        for label, path in self.target_folder_map.items():
            try:
                if self.top_level_folder_name(path, Path(self.base_folder_var.get().strip()).expanduser()) == preferred:
                    return label
            except Exception:
                pass
        for label in self.target_folder_map:
            if label == preferred or label.startswith(preferred + "\\") or label.startswith(preferred + "/"):
                return label
        return next(iter(self.target_folder_map.keys()), None)

    def is_folder_allowed_for_current_user(self, folder: Path, base: Path) -> bool:
        """Schreibrecht für Zielordner nach eigener MySQL-Rechteverwaltung.

        Der lokale Nextcloud-Schreibtest bleibt technische Plausibilitätsprüfung.
        Die fachliche Freigabe erfolgt über Ordnergruppenrechte.
        """
        if self.is_odv_update_path(folder) or any(str(part).upper() == "_ARCHIV" for part in folder.parts):
            return False
        if self.current_role() == "Superadmin":
            return True
        group = self.folder_permission_group(folder, base)
        return self.folder_group_allowed(group, "write")

    def is_folder_readable_for_current_user(self, folder: Path, base: Path) -> bool:
        """Leserecht für Dateiansicht.

        00_ORTSCHRONIK ist der zentrale Lesebereich der Anwendung und wird in
        „Dateien anzeigen“ für alle Rollen vollständig rekursiv angezeigt.
        Schreibrechte werden davon nicht abgeleitet; Bearbeiten/Speichern wird
        separat geprüft. Technische Updateordner bleiben ausgeblendet.
        """
        if self.is_odv_update_path(folder):
            return False
        if self.current_role() == "Superadmin":
            return True
        group = self.folder_permission_group(folder, base)
        if group == "00_ORTSCHRONIK":
            return True
        return self.folder_group_allowed(group, "read")

    def is_file_view_path_in_readable_branch(self, path: Path, base: Path) -> bool:
        """True, wenn path in einem für „Dateien anzeigen“ lesbaren Bereich liegt.

        Wichtig für v77: Die Dateiansicht verwendet für Admins und Bearbeiter
        dieselbe physische Rekursion wie Superadmin. Gefiltert wird nur auf
        Ebene der ODV-Haupt-/Ortsbereiche. Sobald ein lesbarer Bereich erkannt
        ist, werden alle Unterordner darunter angezeigt.
        """
        if self.is_hidden_system_path(path):
            return False
        if self.current_role() == "Superadmin":
            return True
        try:
            rel_parts = path.relative_to(base).parts
        except Exception:
            rel_parts = path.parts
        if not rel_parts:
            return True

        fixed_names = [
            "00_ORTSCHRONIK",
            "01_ABLAGE_ORTSCHRONIK",
            "02_AUSTAUSCH",
            "03_INFORMATION",
            "05_ORGA_CHRONISTEN",
            "06_UNSERE_ARBEITEN",
            "06_ARBEIT_DER_ORTSCHRONISTEN",
        ]
        fixed_tokens = {self.normalize_folder_token(name): name for name in fixed_names}
        for part in rel_parts:
            token = self.normalize_folder_token(part)
            if token in fixed_tokens:
                group = fixed_tokens[token]
                if group in {"00_ORTSCHRONIK", "06_ARBEIT_DER_ORTSCHRONISTEN"}:
                    # 00_ORTSCHRONIK ist Lesebereich; 06_ARBEIT... als realer Ordnername
                    # auf die Rechtegruppe 06_UNSERE_ARBEITEN abbilden.
                    return True if group == "00_ORTSCHRONIK" else self.folder_group_allowed("06_UNSERE_ARBEITEN", "read")
                return self.folder_group_allowed(group, "read")

        # Ortsordner: eigener Ort lesen, andere Orte nur bei entsprechendem Recht.
        group = self.folder_permission_group(path if path.is_dir() else path.parent, base)
        return self.folder_group_allowed(group, "read")

    def can_edit_file_view_metadata(self, path: Path | None = None, item: dict | None = None) -> bool:
        """Fachliche Bearbeitungsberechtigung in „Dateien anzeigen".

        Erlaubt ist Bearbeiten/Speichern, wenn Admin/Superadmin angemeldet ist,
        Schreibrecht auf den Ordner besteht oder es sich um eine eigene bereits
        erfasste Datei handelt. Fehlt „Erfasst von", ist Bearbeitung trotzdem
        erlaubt, wenn Ordnerschreibrecht besteht, z. B. beim zuständigen OC Eicha.
        """
        path = path or self.file_view_current_path
        if not path or not path.exists() or path.is_dir():
            return False
        if self.is_current_admin():
            return True
        item = item if item is not None else (self.file_view_current_metadata or {})

        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        try:
            if self.is_folder_allowed_for_current_user(path.parent, base):
                return True
        except Exception:
            pass

        if item and item.get("upload_id"):
            return self.is_selected_document_owner(item)
        return False

    def api_user_to_local(self, user: dict) -> dict:
        return {
            "display_name": user.get("display_name") or user.get("name") or user.get("username") or "Ortschronist/in",
            "username": user.get("username") or "",
            "password_hash": "",
            "role": self.api_role_to_local(str(user.get("role", "ortschronist"))),
            "place": user.get("place") or "",
            "active": True,
            "api_id": user.get("id"),
        }

    def get_device_info(self) -> dict:
        """Erzeugt/liest die lokale ODV-Gerätekennung und liefert Login-Geräteinfos."""
        device_id = str(self.config_data.get("device_id", "") or "").strip()
        if not device_id:
            device_id = str(uuid.uuid4())
            self.config_data["device_id"] = device_id
            save_config(self.config_data)
        try:
            device_name = socket.gethostname()
        except Exception:
            device_name = platform.node() or "unbekannt"
        try:
            windows_user = getpass.getuser()
        except Exception:
            windows_user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        return {
            "device_id": device_id,
            "device_name": device_name,
            "windows_user": windows_user,
            "os_name": platform.system(),
            "os_version": platform.version(),
            "app_version": APP_VERSION,
        }

    def report_current_device_version(self) -> None:
        """Meldet die aktuelle ODV-Version an die API, damit Sitzungen/Geräte nach Updates aktuell bleiben."""
        try:
            if self.api_token and hasattr(self.api, "update_session_device"):
                self.api.update_session_device(self.api_token, self.get_device_info())
        except Exception as exc:
            app_log_exception("Geräte-/Sitzungsversion konnte nicht aktualisiert werden", exc)

    def handle_login_session_notice(self, response: dict) -> None:
        """Zeigt Hinweise zu neuem Gerät oder Mehrfachanmeldung dezent an."""
        try:
            device = response.get("device") or {}
            sessions = response.get("sessions") or {}
            messages = []
            if device.get("is_new"):
                messages.append("Dieses Gerät wurde erstmals für dieses Benutzerkonto verwendet. Der Superadmin wurde informiert.")
            if int(sessions.get("active_count", 0) or 0) > 1:
                messages.append(f"Hinweis: Dieses Benutzerkonto ist aktuell auf {sessions.get('active_count')} Geräten/Sitzungen aktiv.")
            if messages:
                self.after(400, lambda: messagebox.showinfo("ODV-Anmeldung", "\n\n".join(messages), parent=self))
        except Exception:
            pass

    def authenticate_startup_user(self) -> bool:
        """Anmeldung über die Server-API.

        Ein gültiges Token aus der letzten Anmeldung wird wiederverwendet.
        Ist kein Token vorhanden oder abgelaufen, erscheint der Login-Dialog.
        """
        self.api = APIClient(self.config_data.get("api_url", "https://ortschronik.info/api"))
        self.api_token = str(self.config_data.get("api_token", "") or "")
        self.folder_permissions: dict[str, dict[str, bool]] = {}
        self.place_folder_map: dict[str, str] = {}
        if self.api_token:
            try:
                response = self.api.me(self.api_token)
                user = self.api_user_to_local(response.get("user", {}))
                self.set_current_user(user, persist=True)
                self.report_current_device_version()
                return True
            except ApiError as exc:
                app_log_exception("Gespeichertes API-Token konnte nicht verwendet werden", exc)
                self.config_data["api_token"] = ""
                self.config_data["api_token_expires_at"] = ""
                save_config(self.config_data)
                self.api_token = ""
        return self.open_startup_login_window()

    def open_startup_login_window(self) -> bool:
        """Zeigt beim Programmstart eine robuste Anmeldung direkt im Hauptfenster.

        Einige Windows/Tkinter-Konstellationen zeigen ein Toplevel-Loginfenster
        nicht zuverlässig, solange die Hauptoberfläche noch nicht aufgebaut ist.
        Deshalb wird beim Start das Root-Fenster selbst als Loginfenster genutzt.
        Erst nach erfolgreicher Anmeldung wird die eigentliche Anwendung erzeugt.
        """
        try:
            for child in list(self.winfo_children()):
                child.destroy()
        except Exception:
            pass

        self.title(f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION} – Anmeldung")
        self.geometry("560x300")
        self.minsize(520, 260)
        self.deiconify()
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(800, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

        for idx in range(3):
            self.columnconfigure(idx, weight=0)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame = ttk.Frame(self, padding=24)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=APP_NAME, font=("", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(frame, text=f"{APP_SHORT_NAME} · {APP_VERSION}").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 18))

        ttk.Label(frame, text="Benutzername:").grid(row=2, column=0, sticky="w", pady=6)
        username_var = tk.StringVar(value=self.config_data.get("current_username", ""))
        username_entry = ttk.Entry(frame, textvariable=username_var, width=34)
        username_entry.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=6)

        ttk.Label(frame, text="Passwort:").grid(row=3, column=0, sticky="w", pady=6)
        password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=password_var, show="*", width=34)
        password_entry.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=6)

        api_info = f"Anmeldung über API: {self.config_data.get('api_url', 'https://ortschronik.info/api')}"
        ttk.Label(frame, text=api_info, wraplength=500).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 12))

        done = tk.BooleanVar(value=False)
        result = {"ok": False}

        def do_login(event=None):
            username = username_var.get().strip()
            password = password_var.get()
            if not username or not password:
                messagebox.showerror("Anmeldung", "Bitte Benutzername und Passwort eingeben.", parent=self)
                return
            try:
                self.api = APIClient(self.config_data.get("api_url", "https://ortschronik.info/api"))
                response = self.api.login(username, password, self.get_device_info())
                self.api_token = str(response.get("token", ""))
                self.config_data["api_token"] = self.api_token
                self.config_data["api_token_expires_at"] = str(response.get("expires_at", ""))
                self.config_data["current_username"] = username
                user = self.api_user_to_local(response.get("user", {}))
                self.set_current_user(user, persist=True)
                self.handle_login_session_notice(response)
                self.report_current_device_version()
                result["ok"] = True
                done.set(True)
            except ApiError as exc:
                app_log_exception("Anmeldung fehlgeschlagen", exc, username=username)
                messagebox.showerror("Anmeldung", str(exc), parent=self)

        def cancel():
            result["ok"] = False
            done.set(True)

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(btns, text="Anmelden", command=do_login).pack(side="left", padx=6)
        ttk.Button(btns, text="Abbrechen", command=cancel).pack(side="left", padx=6)

        self.bind("<Return>", do_login)
        self.protocol("WM_DELETE_WINDOW", cancel)
        username_entry.focus_set() if not username_var.get().strip() else password_entry.focus_set()
        self.update_idletasks()
        self.wait_variable(done)
        self.unbind("<Return>")

        try:
            frame.destroy()
            self.protocol("WM_DELETE_WINDOW", self.destroy)
        except Exception:
            pass
        return bool(result["ok"])

    def open_login_dialog(self) -> bool:
        # Der Dialog muss auch dann zuverlässig erscheinen, wenn noch keine
        # Hauptoberfläche aufgebaut ist oder kein gültiger Benutzer geladen werden kann.
        try:
            self.deiconify()
            self.lift()
            self.update_idletasks()
        except Exception:
            pass
        dialog = tk.Toplevel(self)
        dialog.title("Anmeldung")
        try: self.track_window_geometry(dialog, "Anmeldung")
        except Exception: pass
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.columnconfigure(1, weight=1)
        dialog.attributes("-topmost", True)
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()

        ttk.Label(dialog, text=f"{APP_NAME} ({APP_SHORT_NAME})", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        ttk.Label(dialog, text="Benutzername:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        username_var = tk.StringVar(value=self.config_data.get("current_username", ""))
        username_entry = ttk.Entry(dialog, textvariable=username_var, width=34)
        username_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        ttk.Label(dialog, text="Passwort:").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        password_var = tk.StringVar()
        password_entry = ttk.Entry(dialog, textvariable=password_var, show="*", width=34)
        password_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=6)

        api_info = f"Anmeldung über API: {self.config_data.get('api_url', 'https://ortschronik.info/api')}"
        info = ttk.Label(dialog, text=api_info, wraplength=430)
        info.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 8))

        result = {"ok": False}

        def do_login(event=None):
            username = username_var.get().strip()
            password = password_var.get()
            if not username or not password:
                messagebox.showerror("Anmeldung", "Bitte Benutzername und Passwort eingeben.", parent=dialog)
                return
            try:
                self.api = APIClient(self.config_data.get("api_url", "https://ortschronik.info/api"))
                response = self.api.login(username, password, self.get_device_info())
                self.api_token = str(response.get("token", ""))
                self.config_data["api_token"] = self.api_token
                self.config_data["api_token_expires_at"] = str(response.get("expires_at", ""))
                self.config_data["current_username"] = username
                user = self.api_user_to_local(response.get("user", {}))
                self.set_current_user(user, persist=True)
                self.handle_login_session_notice(response)
                self.report_current_device_version()
                result["ok"] = True
                dialog.destroy()
            except ApiError as exc:
                app_log_exception("Anmeldung fehlgeschlagen", exc, username=username)
                messagebox.showerror("Anmeldung", str(exc), parent=dialog)

        def cancel():
            result["ok"] = False
            dialog.destroy()

        btns = ttk.Frame(dialog)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=12, pady=12)
        ttk.Button(btns, text="Anmelden", command=do_login).pack(side="left", padx=6)
        ttk.Button(btns, text="Abbrechen", command=cancel).pack(side="left", padx=6)
        dialog.bind("<Return>", do_login)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        username_entry.focus_set()

        dialog.update_idletasks()
        x = self.winfo_screenwidth() // 2 - dialog.winfo_width() // 2
        y = self.winfo_screenheight() // 3 - dialog.winfo_height() // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.after(300, lambda: dialog.attributes("-topmost", False))
        dialog.focus_force()
        self.wait_window(dialog)
        return bool(result["ok"])


    def logout_and_login(self) -> None:
        """Benutzer wechseln, ohne den aktuellen Benutzer bei Abbruch zu verlieren.

        Der bisherige Benutzer bleibt angemeldet, solange der neue Login nicht
        erfolgreich abgeschlossen wurde. Dadurch entsteht kein Zwischenzustand
        ohne gültigen Benutzer/Token.
        """
        old_token = self.api_token
        old_user = dict(self.current_user or {})
        old_config_token = str(self.config_data.get("api_token", "") or "")
        old_config_expires = str(self.config_data.get("api_token_expires_at", "") or "")
        old_username = str(self.config_data.get("current_username", "") or "")
        old_display = str(self.config_data.get("display_name", "") or "")
        old_role = str(self.config_data.get("current_role", "") or "")
        old_place = str(self.config_data.get("current_place", "") or "")

        if self.open_login_dialog():
            # Erst nach erfolgreichem neuem Login den alten Token serverseitig abmelden.
            if old_token and old_token != self.api_token:
                try:
                    self.api.logout(old_token)
                except ApiError as exc:
                    app_log_exception("Logout des vorherigen API-Tokens fehlgeschlagen", exc)
            self.apply_selected_user()
            self.refresh_history()
            self.load_folders_from_config()
            self.update_tab_labels()
            return

        # Abbruch: alten Zustand vollständig wiederherstellen.
        if old_user:
            self.current_user = old_user
        self.api_token = old_token or old_config_token
        self.config_data["api_token"] = old_config_token
        self.config_data["api_token_expires_at"] = old_config_expires
        self.config_data["current_username"] = old_username
        self.config_data["display_name"] = old_display
        self.config_data["current_role"] = old_role
        self.config_data["current_place"] = old_place
        save_config(self.config_data)
        if old_user:
            self.set_current_user(old_user, persist=True)
            self.refresh_window_title()

    def set_current_user(self, user: dict, persist: bool = True) -> None:
        self.current_user = user
        self.display_name_var.set(user.get("display_name", ""))
        self.username_var.set(user.get("username", ""))
        self.role_var.set(user.get("role", "Ortschronist"))
        self.role_label_var.set(self.role_var.get())
        self.place_var.set(user.get("place", ""))
        # Beim Benutzerwechsel muss der Ort im Upload-Formular sofort zum neu angemeldeten Benutzer passen.
        if hasattr(self, "meta_vars") and "place" in self.meta_vars:
            self.meta_vars["place"].set(self.place_var.get().strip())
        self.config_data["display_name"] = self.display_name_var.get()
        self.config_data["current_username"] = self.username_var.get()
        self.config_data["current_role"] = self.role_var.get()
        self.config_data["current_place"] = self.place_var.get()
        self.load_current_folder_permissions()
        if persist:
            save_config(self.config_data)

    def refresh_window_title(self) -> None:
        name = self.config_data.get("display_name") or "Ortschronist/in"
        role = self.config_data.get("current_role") or ""
        self.title(f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION} API – {name} ({role})")

    def make_scrollable_tab(self, parent: ttk.Frame) -> ttk.Frame:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        return frame

    def open_masterdata_dialog(self) -> None:
        """Stammdaten über Datei > Stammdaten.

        Der Benutzername/Name/Rolle stammen aus der Benutzerverwaltung. Hier wird
        nur das lokale Nextcloud-Stammverzeichnis gepflegt.
        """
        dialog = tk.Toplevel(self)
        dialog.title("Stammdaten")
        try: self.track_window_geometry(dialog, "Stammdaten")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        dialog.resizable(True, False)

        ttk.Label(dialog, text="Stammdaten", font=("", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))

        ttk.Label(dialog, text="Name:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ttk.Label(dialog, textvariable=self.display_name_var).grid(row=1, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(dialog, text="Benutzername:").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ttk.Label(dialog, textvariable=self.username_var).grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(dialog, text="Rolle:").grid(row=3, column=0, sticky="w", padx=12, pady=6)
        ttk.Label(dialog, textvariable=self.role_label_var).grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(dialog, text="Ort des Ortschronisten:").grid(row=4, column=0, sticky="w", padx=12, pady=6)
        ttk.Label(dialog, textvariable=self.place_var).grid(row=4, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(dialog, text="Nextcloud-Stammverzeichnis:").grid(row=5, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(dialog, textvariable=self.base_folder_var, width=80).grid(row=5, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(dialog, text="Auswählen", command=lambda: self.choose_base_folder(parent=dialog)).grid(row=5, column=2, sticky="e", padx=12, pady=6)

        self.ensure_standard_metadata_folder()
        ttk.Label(dialog, text="Metadatenordner:").grid(row=6, column=0, sticky="w", padx=12, pady=6)
        ttk.Label(dialog, textvariable=self.metadata_folder_var).grid(row=6, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        hint = (
            "Der Metadatenordner wird automatisch unterhalb des Nextcloud-Stammverzeichnisses "
            "als .ortschronik_metadaten gesetzt. Benutzer wählen ihn nicht selbst aus."
        )
        ttk.Label(dialog, text=hint, wraplength=820).grid(row=7, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))

        buttons = ttk.Frame(dialog)
        buttons.grid(row=8, column=0, columnspan=3, sticky="e", padx=12, pady=12)
        ttk.Button(buttons, text="Ordner prüfen", command=lambda: self.load_writable_folders(show_message=True)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Stammdaten speichern", command=lambda: self.save_masterdata_and_close(dialog)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=6)

        dialog.update_idletasks()
        x = self.winfo_rootx() + max(40, (self.winfo_width() - dialog.winfo_width()) // 2)
        y = self.winfo_rooty() + max(40, (self.winfo_height() - dialog.winfo_height()) // 4)
        dialog.geometry(f"+{x}+{y}")

    def save_masterdata_and_close(self, dialog: tk.Toplevel) -> None:
        self.save_basic_config(show_message=True)
        dialog.destroy()

    def user_names(self) -> list[str]:
        return [str(u.get("display_name", "")) for u in self.users if u.get("active", True)]

    def current_role(self) -> str:
        return self.role_var.get().strip() if hasattr(self, "role_var") else self.config_data.get("current_role", "Ortschronist")

    def is_current_admin(self) -> bool:
        return role_allows_admin(self.current_role())

    def apply_selected_user(self) -> None:
        # In der API-Version ist die angemeldete Person bereits durch /login oder /me gesetzt.
        # Die frühere lokale users.json darf diese Daten nicht mehr überschreiben.
        if self.current_user:
            self.role_label_var.set(self.role_var.get())
            if hasattr(self, "meta_vars") and "place" in self.meta_vars:
                self.meta_vars["place"].set(self.place_var.get().strip())
        else:
            username = self.username_var.get().strip() or self.config_data.get("current_username", "")
            user = find_user_by_username(self.users, username) if username else None
            if user:
                self.set_current_user(user, persist=True)
            else:
                self.role_label_var.set(self.role_var.get())
        self.refresh_window_title()
        if hasattr(self, "notebook") and hasattr(self, "admin_tab"):
            # Seit v54 dürfen auch normale Bearbeiter eigene, noch nicht übernommene
            # Dokumente im Reiter „Dateien bearbeiten“ ergänzen. Admin-/Superadmin-
            # Funktionen werden in der Oberfläche separat ein-/ausgeblendet.
            try:
                if not getattr(self, "admin_tab_visible", True):
                    self.notebook.add(self.admin_tab, text="Dateien bearbeiten")
                    self.admin_tab_visible = True
                self.configure_admin_actions_for_role()
            except tk.TclError:
                pass
        # Menü je nach Rolle neu aufbauen, damit Admin-Menü nur Superadmins sehen.
        if hasattr(self, "notebook"):
            self.create_menu()

    def require_admin(self) -> bool:
        self.apply_selected_user()
        if self.is_current_admin():
            return True
        messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Admins freigegeben.")
        return False

    def create_file_view_tab(self) -> None:
        self.viewer_tab.columnconfigure(0, weight=1)
        self.viewer_tab.rowconfigure(0, weight=1)

        self.viewer_outer_pane = ttk.PanedWindow(self.viewer_tab, orient=tk.HORIZONTAL)
        self.viewer_outer_pane.grid(row=0, column=0, sticky="nsew")
        self.viewer_outer_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())

        tree_frame = ttk.LabelFrame(self.viewer_outer_pane, text="Dateien", padding=8)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(2, weight=1)
        ttk.Label(tree_frame, text="Verzeichnis:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.file_view_root_var = tk.StringVar(value=self.config_data.get("file_view_root", self.base_folder_var.get()) or self.base_folder_var.get())
        self.file_view_combo = ttk.Combobox(tree_frame, textvariable=self.file_view_root_var, state="readonly")
        self.file_view_combo.grid(row=0, column=0, sticky="ew", padx=(85, 118), pady=(0, 6))
        self.file_view_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_file_view_root_selected())
        ttk.Button(tree_frame, text="Baum...", command=self.choose_file_view_root_tree).grid(row=0, column=0, sticky="e", padx=(8, 0), pady=(0, 6))

        filter_frame = ttk.Frame(tree_frame)
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Suche/Filter:").grid(row=0, column=0, sticky="w")
        self.file_view_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.file_view_filter_var).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(filter_frame, text="Suchen", command=self.refresh_file_view_tree).grid(row=0, column=2, sticky="e")
        ttk.Button(filter_frame, text="Zurücksetzen", command=self.clear_file_view_filter).grid(row=0, column=3, sticky="e", padx=(6, 0))

        self.file_tree = ttk.Treeview(tree_frame, columns=("path",), show="tree")
        self.file_tree.tag_configure("folder_has_files", background="#fff2cc")
        self.file_tree.tag_configure("without_odv_metadata", foreground="#777777")
        self.file_tree.grid(row=2, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", lambda _e: self.on_file_tree_select())
        self.file_tree.bind("<Double-1>", lambda _e: self.open_selected_file_from_tree())
        self.file_tree.bind("<Button-3>", self.show_file_tree_context_menu)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=2, column=1, sticky="ns")
        hsb.grid(row=3, column=0, sticky="ew")

        right_pane = ttk.PanedWindow(self.viewer_outer_pane, orient=tk.VERTICAL)
        self.viewer_right_pane = right_pane
        self.viewer_outer_pane.add(tree_frame, weight=1)
        self.viewer_outer_pane.add(right_pane, weight=2)

        preview_frame = ttk.LabelFrame(right_pane, text="Vorschau / Personen", padding=8)
        preview_frame.columnconfigure(0, weight=0)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        self.show_persons_var = tk.BooleanVar(value=True)
        self.show_persons_check = ttk.Checkbutton(preview_frame, text="Personen anzeigen", variable=self.show_persons_var, command=self.show_file_preview)
        self.show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.show_persons_check.grid_remove()
        self.file_view_open_ocr_button = ttk.Button(preview_frame, text="OCR anzeigen", command=self.open_file_view_ocr_pdf, state="disabled")
        self.file_view_open_ocr_button.grid(row=0, column=1, sticky="e", pady=(0, 6))
        self.person_legend_text, legend_frame = self.make_scrolled_text(preview_frame, height=8, wrap="word")
        self.person_legend_frame = legend_frame
        legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.person_legend_text.configure(width=32, state="disabled")
        self.file_preview_label = ttk.Label(preview_frame, text="Keine Datei ausgewählt.", anchor="center")
        self.file_preview_label.grid(row=1, column=1, sticky="nsew")
        self.file_preview_label.bind("<Double-1>", lambda _e: self.edit_persons_for_current_file())

        meta_outer = ttk.LabelFrame(right_pane, text="Metadaten", padding=8)
        meta_outer.columnconfigure(0, weight=1)
        meta_outer.rowconfigure(0, weight=1)
        meta_canvas = tk.Canvas(meta_outer, highlightthickness=0)
        meta_scroll = ttk.Scrollbar(meta_outer, orient="vertical", command=meta_canvas.yview)
        meta_frame = ttk.Frame(meta_canvas)
        meta_window = meta_canvas.create_window((0, 0), window=meta_frame, anchor="nw")
        meta_frame.bind("<Configure>", lambda _e: meta_canvas.configure(scrollregion=meta_canvas.bbox("all")))
        meta_canvas.bind("<Configure>", lambda e: meta_canvas.itemconfigure(meta_window, width=e.width))
        meta_canvas.configure(yscrollcommand=meta_scroll.set)
        meta_canvas.grid(row=0, column=0, sticky="nsew")
        meta_scroll.grid(row=0, column=1, sticky="ns")
        self.file_view_meta_canvas = meta_canvas
        for scroll_widget in (meta_canvas, meta_frame):
            scroll_widget.bind("<Enter>", lambda _e: meta_canvas.bind_all("<MouseWheel>", self.on_file_view_meta_mousewheel))
            scroll_widget.bind("<Leave>", lambda _e: meta_canvas.unbind_all("<MouseWheel>"))

        self.file_view_write_hint_var = tk.StringVar(value="")
        ttk.Label(meta_frame, textvariable=self.file_view_write_hint_var).grid(row=0, column=0, sticky="w", pady=(0, 6))
        metadata_form_frame = ttk.Frame(meta_frame)
        metadata_form_frame.grid(row=1, column=0, sticky="nsew")
        meta_frame.columnconfigure(0, weight=1)
        meta_frame.rowconfigure(1, weight=1)
        form = self.create_metadata_form_two_columns(metadata_form_frame, "file_view")
        self.file_view_meta_vars = form["vars"]  # type: ignore[assignment]
        self.file_view_meta_widgets = form["widgets"]  # type: ignore[assignment]
        self.file_view_description_text = form["description_text"]  # type: ignore[assignment]
        self.file_view_description_counter_var = form.get("description_counter_var")  # type: ignore[assignment]
        self.file_view_note_text = form["note_text"]  # type: ignore[assignment]
        self.file_view_json_text = form["json_text"]  # type: ignore[assignment]

        right_pane.add(preview_frame, weight=1)
        right_pane.add(meta_outer, weight=3)
        self.after(200, self.restore_pane_positions)
        self.refresh_file_view_folder_choices()

    def on_file_view_meta_mousewheel(self, event) -> None:
        canvas = getattr(self, "file_view_meta_canvas", None)
        if canvas is None:
            return
        delta = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
        if delta:
            canvas.yview_scroll(delta, "units")

    def clear_file_view_filter(self) -> None:
        if hasattr(self, "file_view_filter_var"):
            self.file_view_filter_var.set("")
        self.refresh_file_view_tree()

    def refresh_file_view_folder_choices(self) -> None:
        if not hasattr(self, "file_view_combo"):
            return
        base = self.nextcloud_base_path(show_message=False)
        self.file_view_folder_map = {}
        if base is not None and base.exists():
            candidates: list[Path] = [base]
            try:
                for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
                    if child.is_dir() and not self.is_hidden_system_path(child) and self.is_file_view_path_in_readable_branch(child, base):
                        candidates.append(child)
                        # ODV-Hauptordner unter Sammelordnern zusätzlich anbieten.
                        try:
                            for sub in sorted(child.iterdir(), key=lambda p: p.name.lower()):
                                if sub.is_dir() and not self.is_hidden_system_path(sub) and self.is_file_view_path_in_readable_branch(sub, base):
                                    candidates.append(sub)
                        except OSError:
                            pass
            except OSError:
                pass
            for folder in sorted(set(candidates), key=lambda p: str(p).lower()):
                label = self.display_path_for_folder(folder, base)
                self.file_view_folder_map[label] = folder
        values = list(self.file_view_folder_map.keys())
        self.file_view_combo["values"] = values
        current = self.file_view_root_var.get().strip()
        if values:
            if current in self.file_view_folder_map:
                self.file_view_root_var.set(current)
            else:
                selected = None
                for label, path in self.file_view_folder_map.items():
                    if str(path) == current:
                        selected = label
                        break
                self.file_view_root_var.set(selected or values[0])
            self.refresh_file_view_tree()

    def on_file_view_root_selected(self) -> None:
        self.config_data["file_view_root"] = self.file_view_root_var.get().strip()
        save_config(self.config_data)
        self.refresh_file_view_tree()

    def choose_file_view_root(self) -> None:
        folder = filedialog.askdirectory(title="Verzeichnis für Dateiansicht auswählen")
        if folder:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            path = Path(folder).expanduser()
            if self.is_odv_update_path(path):
                messagebox.showwarning("Systemordner", "Der Ordner ODV_UPDATE ist ein technischer Updateordner und kann hier nicht ausgewählt werden.")
                return
            label = self.display_path_for_folder(path, base) if base.exists() else self.normalize_local_path_text(path)
            self.file_view_folder_map[label] = path
            self.file_view_combo["values"] = list(self.file_view_folder_map.keys())
            self.file_view_root_var.set(label)
            self.on_file_view_root_selected()

    def choose_file_view_root_tree(self) -> None:
        self.refresh_file_view_folder_choices()
        folders = list(self.file_view_folder_map.values())
        selected = self.open_folder_tree_dialog("Verzeichnis für Dateiansicht auswählen", folders, self.file_view_root_var.get())
        if selected:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            label = self.display_path_for_folder(selected, base)
            self.file_view_folder_map[label] = selected
            values = list(self.file_view_combo["values"])
            if label not in values:
                values.append(label)
                values.sort(key=str.lower)
                self.file_view_combo["values"] = values
            self.file_view_root_var.set(label)
            self.on_file_view_root_selected()

    def refresh_file_view_tree(self) -> None:
        if not hasattr(self, "file_tree"):
            return
        root_text = self.file_view_root_var.get().strip() or self.base_folder_var.get().strip()
        if not root_text:
            return
        root = self.file_view_folder_map.get(root_text, Path(root_text).expanduser())
        if not root.exists() or not root.is_dir():
            messagebox.showwarning("Verzeichnis", f"Verzeichnis nicht gefunden:\n{root}")
            return
        self.file_view_metadata_items = load_metadata_files(self.metadata_folder_path())
        self.file_view_metadata_by_path = {}
        for item in self.file_view_metadata_items:
            p = str(item.get("current_path", "") or "")
            if p:
                self.file_view_metadata_by_path[str(Path(p))] = item
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        root_tags = ("folder_has_files",) if self.folder_contains_files(root) else ()
        root_id = self.file_tree.insert("", "end", text=root.name or str(root), values=(str(root),), open=True, tags=root_tags)
        self._add_file_tree_children(root_id, root, depth=0)

    def current_file_view_filter_norm(self) -> str:
        if not hasattr(self, "file_view_filter_var"):
            return ""
        return self.normalize_search_text(self.file_view_filter_var.get())

    def file_matches_current_filter(self, path: Path) -> bool:
        term = self.current_file_view_filter_norm()
        if not term:
            return True
        hay = [path.name]
        try:
            item = getattr(self, "file_view_metadata_by_path", {}).get(str(path)) or {}
            hay.extend([str(item.get("keywords") or ""), str(item.get("description") or "")])
        except Exception:
            pass
        return any(term in self.normalize_search_text(x) for x in hay)

    def is_linked_ocr_file_path(self, path: Path) -> bool:
        """OCR-Arbeitskopien werden über das Original geöffnet, nicht als eigenes Dokument."""
        try:
            if path.suffix.lower() != ".pdf":
                return False
            if path.stem.lower().endswith("_ocr"):
                return True
            path_text = str(path)
            for item in getattr(self, "file_view_metadata_items", []) or []:
                ocr_text = str(item.get("ocr_pdf_path") or item.get("ocr_current_path") or "").strip()
                if ocr_text and str(Path(ocr_text)) == path_text:
                    return True
        except Exception:
            pass
        return False

    def folder_contains_files(self, folder: Path) -> bool:
        """True, wenn der Ordner selbst oder irgendein Unterordner sichtbare Dateien enthält.

        Berücksichtigt Systemdateien, Leserechte und optional den Dateinamenfilter.
        """
        base = Path(self.base_folder_var.get().strip()).expanduser()
        try:
            for child in folder.iterdir():
                if self.is_hidden_system_path(child):
                    continue
                readable_target = child if child.is_dir() else folder
                if not self.is_file_view_path_in_readable_branch(readable_target, base):
                    continue
                if child.is_file() and not self.is_linked_ocr_file_path(child) and self.file_matches_current_filter(child):
                    return True
                if child.is_dir() and self.folder_contains_files(child):
                    return True
        except OSError:
            return False
        return False

    def _add_file_tree_children(self, parent_id: str, folder: Path, depth: int = 0) -> None:
        try:
            children = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        base = Path(self.base_folder_var.get().strip()).expanduser()
        filter_active = bool(self.current_file_view_filter_norm())
        for child in children:
            if self.is_hidden_system_path(child):
                continue

            readable_target = child if child.is_dir() else folder
            if not self.is_file_view_path_in_readable_branch(readable_target, base):
                continue

            if child.is_dir():
                has_matching_files = self.folder_contains_files(child)
                if filter_active and not has_matching_files:
                    continue
                tags = ("folder_has_files",) if has_matching_files else ()
                node = self.file_tree.insert(parent_id, "end", text=child.name, values=(str(child),), open=False, tags=tags)
                # v77: bewusst vollständig rekursiv einfügen, damit Bearbeiter/Admin
                # denselben Baum wie Superadmins sehen. Performance wird über
                # Systemdatei-Filter und kleinere Root-Auswahl abgefangen.
                self._add_file_tree_children(node, child, depth + 1)
            else:
                if self.is_linked_ocr_file_path(child):
                    continue
                if not self.file_matches_current_filter(child):
                    continue
                tags = ()
                if str(child) not in self.file_view_metadata_by_path:
                    tags = ("without_odv_metadata",)
                self.file_tree.insert(parent_id, "end", text=child.name, values=(str(child),), open=False, tags=tags)

    def on_file_tree_select(self) -> None:
        sel = self.file_tree.selection()
        if not sel:
            return
        values = self.file_tree.item(sel[0], "values")
        if not values:
            return
        path = Path(values[0])
        self.file_view_current_path = path
        self.file_view_current_metadata = self.file_view_metadata_by_path.get(str(path))
        self.show_file_preview()
        self.load_file_view_metadata_form()
        self.update_file_view_ocr_button()

    def open_selected_file_from_tree(self) -> None:
        """Öffnet die aktuell ausgewählte Datei mit der Standardanwendung des Betriebssystems.

        Das ist vor allem für PDF, Word, Tabellen usw. gedacht. Bilddateien können
        zusätzlich weiterhin über die Vorschau/Personenzuordnung bearbeitet werden.
        """
        sel = self.file_tree.selection()
        if not sel:
            return
        values = self.file_tree.item(sel[0], "values")
        if not values:
            return
        path = Path(values[0])
        if not path.exists() or path.is_dir():
            return
        self.open_file_with_default_app(path)

    def open_file_with_default_app(self, path: Path) -> None:
        try:
            system = platform.system().lower()
            if system == "windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif system == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            app_log("info", "Datei mit Standardprogramm geöffnet", path=str(path))
            self.log_document_access(path, "opened")
        except Exception as exc:
            app_log_exception("Datei konnte nicht geöffnet werden", exc)
            messagebox.showerror("Datei öffnen", f"Die Datei konnte nicht geöffnet werden:\n{path}\n\n{exc}")

    def resolve_item_ocr_pdf_path(self, item: dict | None) -> Path | None:
        if not item:
            return None
        for key in ("ocr_pdf_path", "ocr_current_path"):
            text = str(item.get(key) or "").strip()
            if text:
                path = Path(text).expanduser()
                if path.exists() and path.is_file():
                    return path
        current_text = str(item.get("current_path") or "").strip()
        if current_text:
            current = Path(current_text).expanduser()
            candidate = current.with_name(f"{current.stem}_ocr.pdf")
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def update_file_view_ocr_button(self) -> None:
        if not hasattr(self, "file_view_open_ocr_button"):
            return
        path = self.resolve_item_ocr_pdf_path(getattr(self, "file_view_current_metadata", None))
        self.file_view_open_ocr_button.configure(state=("normal" if path else "disabled"))

    def open_file_view_ocr_pdf(self) -> None:
        path = self.resolve_item_ocr_pdf_path(getattr(self, "file_view_current_metadata", None))
        if not path:
            messagebox.showwarning("OCR anzeigen", "Zu diesem Dokument ist kein OCR-PDF verknüpft.")
            return
        self.open_file_with_default_app(path)

    def item_for_local_path(self, path: Path) -> dict | None:
        """Sucht zu einem lokalen Dateipfad den ODV-Datensatz, falls vorhanden."""
        try:
            key = str(path)
            if hasattr(self, "file_view_metadata_by_path") and key in self.file_view_metadata_by_path:
                return self.file_view_metadata_by_path.get(key)
            for item in getattr(self, "admin_uploads", []) or []:
                self.normalize_admin_item_path_for_current_pc(item)
                candidate = self.resolve_document_local_path(item)
                if candidate and candidate == path:
                    return item
        except Exception:
            pass
        return None

    def log_document_access(self, path: Path, action: str, item: dict | None = None) -> None:
        """Protokolliert Öffnen/Download über ODV in der API-Historie, sofern ein Dokumentdatensatz existiert."""
        item = item or self.item_for_local_path(path)
        upload_id = str((item or {}).get("upload_id") or "")
        if not upload_id or not self.api_token:
            return
        try:
            self.api.log_document_access(self.api_token, upload_id, action, str(path))
        except Exception as exc:
            app_log_exception("Dokumentzugriff konnte nicht protokolliert werden", exc, upload_id=upload_id, action=action)

    def download_file_to_local_folder(self, path: Path, item: dict | None = None) -> None:
        """Kopiert eine Datei aus dem Nextcloud-Syncordner in Downloads oder ein frei gewähltes Zielverzeichnis."""
        if not path.exists() or not path.is_file():
            messagebox.showwarning("Download", "Die Datei wurde lokal nicht gefunden.")
            return
        default_dir = Path.home() / "Downloads"
        if not default_dir.exists():
            default_dir = Path.home()
        target_dir_text = filedialog.askdirectory(title="Zielordner für Download/Kopie auswählen", initialdir=str(default_dir))
        if not target_dir_text:
            return
        target_dir = Path(target_dir_text)
        try:
            target = unique_path_with_counter(target_dir / path.name)
            shutil.copy2(path, target)
            self.log_document_access(path, "downloaded", item)
            add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Benutzer", "Dokument heruntergeladen", f"{path.name} → {target}", (item or {}).get("upload_id")))
            messagebox.showinfo("Download", f"Datei wurde kopiert nach:\n{target}")
        except Exception as exc:
            app_log_exception("Download/Kopie konnte nicht erstellt werden", exc, path=str(path))
            messagebox.showerror("Download", f"Die Datei konnte nicht kopiert werden:\n{exc}")

    def safe_text_lines(self, text: str, max_chars: int = 95) -> list[str]:
        text = " ".join(str(text or "").split())
        if not text:
            return []
        lines: list[str] = []
        while len(text) > max_chars:
            cut = text.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            lines.append(text[:cut].strip())
            text = text[cut:].strip()
        if text:
            lines.append(text)
        return lines

    def create_person_master_sheet_pdf(self, path: Path, item: dict | None = None) -> None:
        """Erzeugt ein A4-Stammdatenblatt für Bilder mit Personenzuordnung."""
        item = item or self.item_for_local_path(path) or {}
        persons = item.get("persons") or []
        if not path.exists() or not is_image_file(path):
            messagebox.showwarning("Stammdatenblatt", "Bitte eine lokal vorhandene Bilddatei auswählen.")
            return
        if not persons:
            messagebox.showwarning("Stammdatenblatt", "Für dieses Bild sind keine Personen zugeordnet.")
            return
        target = filedialog.asksaveasfilename(
            title="Stammdatenblatt als PDF speichern",
            defaultextension=".pdf",
            initialfile=f"{path.stem}_stammdatenblatt.pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        try:
            page_w, page_h = 1240, 1754  # A4 bei ca. 150 dpi
            margin = 70
            page = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(page)
            try:
                font_title = ImageFont.truetype("arial.ttf", 34)
                font_head = ImageFont.truetype("arial.ttf", 24)
                font = ImageFont.truetype("arial.ttf", 20)
                font_small = ImageFont.truetype("arial.ttf", 17)
            except Exception:
                font_title = font_head = font = font_small = ImageFont.load_default()

            title = "ODV-Stammdatenblatt mit Personenzuordnung"
            draw.text((margin, 35), title, fill="black", font=font_title)

            img = Image.open(path).convert("RGB")
            img.thumbnail((page_w - 2 * margin, 780))
            img, _legend = self.draw_person_overlays(img, persons, True, font_size=28)
            img_x = int((page_w - img.width) / 2)
            img_y = 95
            page.paste(img, (img_x, img_y))
            sep_y = 910
            draw.line((margin, sep_y, page_w - margin, sep_y), fill="black", width=2)

            y = sep_y + 25
            draw.text((margin, y), "Personen", fill="black", font=font_head)
            y += 35
            draw.text((margin, y), "Nr.", fill="black", font=font_small)
            draw.text((margin + 70, y), "Name", fill="black", font=font_small)
            draw.text((margin + 460, y), "Sicherheit", fill="black", font=font_small)
            draw.text((margin + 650, y), "Bemerkung", fill="black", font=font_small)
            y += 24
            draw.line((margin, y, page_w - margin, y), fill="#777777", width=1)
            y += 12
            for p in persons[:12]:
                number = str(p.get("number", ""))
                name = str(p.get("name") or p.get("display_name") or "")
                certainty = str(p.get("certainty") or "")
                note = str(p.get("note") or "")
                draw.text((margin, y), number, fill="black", font=font_small)
                draw.text((margin + 70, y), name[:38], fill="black", font=font_small)
                draw.text((margin + 460, y), certainty[:18], fill="black", font=font_small)
                draw.text((margin + 650, y), note[:45], fill="black", font=font_small)
                y += 26
            if len(persons) > 12:
                draw.text((margin, y), f"… weitere Personen: {len(persons) - 12}", fill="black", font=font_small)
                y += 28

            y += 12
            draw.text((margin, y), "Wichtige Dateidaten", fill="black", font=font_head)
            y += 34
            data_pairs = [
                ("Datei", item.get("current_filename") or path.name),
                ("Upload-/Erfassungs-ID", item.get("upload_id") or ""),
                ("Erfasst von", item.get("uploaded_by") or item.get("uploaded_by_name") or ""),
                ("Erfasst am", item.get("uploaded_at") or item.get("created_at") or ""),
                ("Ort", item.get("place") or ""),
                ("Datum / Zeitraum", item.get("document_date") or ""),
                ("Ereignis", item.get("event") or ""),
                ("Primärquelle", item.get("primary_source") or ""),
                ("Sekundärquelle", item.get("secondary_source") or item.get("source") or ""),
                ("Archiv / Signatur", " / ".join([v for v in [str(item.get("archive_name") or ""), str(item.get("archive_signature") or "")] if v])),
                ("Rechte", item.get("rights_note") or item.get("license_note") or ""),
            ]
            for label, value in data_pairs:
                if not value:
                    continue
                draw.text((margin, y), f"{label}:", fill="black", font=font_small)
                draw.text((margin + 260, y), str(value)[:80], fill="black", font=font_small)
                y += 25
            desc_lines = self.safe_text_lines(str(item.get("description") or ""), 85)[:4]
            if desc_lines:
                draw.text((margin, y), "Beschreibung:", fill="black", font=font_small)
                x = margin + 260
                for line in desc_lines:
                    draw.text((x, y), line, fill="black", font=font_small)
                    y += 23
            page.save(target, "PDF", resolution=150.0)
            messagebox.showinfo("Stammdatenblatt", f"Stammdatenblatt wurde erstellt:\n{target}")
        except Exception as exc:
            app_log_exception("Stammdatenblatt konnte nicht erstellt werden", exc, path=str(path))
            messagebox.showerror("Stammdatenblatt", f"PDF konnte nicht erstellt werden:\n{exc}")

    def show_file_tree_context_menu(self, event) -> None:
        iid = self.file_tree.identify_row(event.y)
        if not iid:
            return
        self.file_tree.selection_set(iid)
        values = self.file_tree.item(iid, "values")
        if not values:
            return
        path = Path(values[0])
        if not path.exists() or path.is_dir():
            return
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Datei öffnen", command=lambda: self.open_file_with_default_app(path))
        menu.add_command(label="Download / Kopie speichern unter...", command=lambda: self.download_file_to_local_folder(path))
        item = self.file_view_metadata_by_path.get(str(path)) or self.file_view_current_metadata or {}
        if is_image_file(path) and (item.get("persons") or []):
            menu.add_command(label="Stammdatenblatt als PDF speichern...", command=lambda: self.create_person_master_sheet_pdf(path, item))
        if is_image_file(path) and self.is_current_admin():
            menu.add_command(label="In PDF umwandeln...", command=lambda: self.convert_file_view_image_to_pdf(path))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_admin_tree_context_menu(self, event) -> None:
        iid = self.admin_tree.identify_row(event.y)
        if not iid:
            return
        # Bei Mehrfachauswahl darf ein Rechtsklick auf eine bereits markierte Zeile
        # die Auswahl nicht wieder auf eine Datei reduzieren. Sonst funktioniert
        # „Ausgewählte PDFs zusammenfassen“ praktisch nicht.
        if iid not in self.admin_tree.selection():
            self.admin_tree.selection_set(iid)
        self.show_selected_admin_details()
        item = self.selected_admin_upload()
        if not item:
            return
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        menu = tk.Menu(self, tearoff=False)
        if path and path.exists() and path.is_file():
            menu.add_command(label="Datei öffnen", command=lambda: self.open_file_with_default_app(path))
            menu.add_command(label="Download / Kopie speichern unter...", command=lambda: self.download_file_to_local_folder(path, item))
            if is_image_file(path) and (item.get("persons") or []):
                menu.add_command(label="Stammdatenblatt als PDF speichern...", command=lambda: self.create_person_master_sheet_pdf(path, item))
            if is_image_file(path):
                menu.add_command(label="Bild in PDF umwandeln", command=lambda: self.convert_admin_image_to_pdf(item))
            if len(self.admin_tree.selection()) >= 2:
                menu.add_command(label="Ausgewählte PDFs zusammenfassen...", command=self.merge_selected_admin_pdfs)
        else:
            menu.add_command(label="Datei nicht gefunden", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def open_selected_admin_file(self) -> None:
        """Öffnet die in 'Dateien bearbeiten' gewählte Datei im Standardprogramm."""
        item = self.selected_admin_upload()
        if not item:
            return
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        if not path or not path.exists() or not path.is_file():
            messagebox.showwarning("Datei öffnen", "Die Datei wurde im lokalen Nextcloud-Stammverzeichnis nicht gefunden.")
            return
        self.open_file_with_default_app(path)

    def merge_selected_admin_pdfs(self) -> None:
        if not self.require_admin():
            return
        selected_ids = list(self.admin_tree.selection())
        if len(selected_ids) < 2:
            messagebox.showwarning("PDF zusammenfassen", "Bitte mindestens zwei PDF-Dateien auswählen.")
            return
        # Reihenfolge: so wie die Dateien aktuell in der Liste angezeigt werden.
        ordered_ids = [iid for iid in self.admin_tree.get_children() if iid in selected_ids]
        selected_items = []
        for uid in ordered_ids:
            for item in self.admin_uploads:
                if str(item.get("upload_id")) == str(uid):
                    self.normalize_admin_item_path_for_current_pc(item)
                    selected_items.append(item)
                    break
        pdf_paths: list[Path] = []
        for item in selected_items:
            p = self.resolve_document_local_path(item)
            if p and p.exists() and p.suffix.lower() == ".pdf":
                pdf_paths.append(p)
        if len(pdf_paths) < 2:
            messagebox.showwarning("PDF zusammenfassen", "Unter der Auswahl wurden weniger als zwei lokal vorhandene PDF-Dateien gefunden.")
            return
        default_name = make_normalized_archive_filename(selected_items[0], "zusammenfassung.pdf")
        target = filedialog.asksaveasfilename(
            title="PDF zusammenfassen",
            initialdir=str(pdf_paths[0].parent),
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        target_path = Path(target)
        try:
            from pypdf import PdfReader, PdfWriter
            writer = PdfWriter()
            for pdf in pdf_paths:
                reader = PdfReader(str(pdf))
                for page in reader.pages:
                    writer.add_page(page)
            with target_path.open("wb") as fh:
                writer.write(fh)
        except Exception as exc:
            app_log_exception("PDFs konnten nicht zusammengeführt werden", exc)
            messagebox.showerror("PDF zusammenfassen", f"PDF-Dateien konnten nicht zusammengeführt werden:\n{exc}")
            return
        source_item = dict(selected_items[0]) if selected_items else {}
        merged_item = dict(source_item)
        merged_item["upload_id"] = make_upload_id()
        merged_item["original_filename"] = "; ".join(p.name for p in pdf_paths)
        merged_item["stored_filename"] = target_path.name
        merged_item["current_filename"] = target_path.name
        merged_item["current_path"] = str(target_path)
        merged_item["target_folder"] = str(target_path.parent)
        merged_item["document_type"] = "PDF-Dokument"
        merged_item["status"] = "hochgeladen"
        merged_item["person_status"] = "none"
        merged_item["persons"] = []
        merged_item["history"] = []
        append_metadata_history(
            merged_item,
            self.display_name_var.get().strip() or "Admin",
            "PDFs zusammengeführt",
            " + ".join(p.name for p in pdf_paths) + f" → {target_path.name}",
        )
        api_ok, api_msg, metadata_file = self.register_pdf_item(merged_item)
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "PDFs zusammengeführt", f"{len(pdf_paths)} PDF-Dateien → {target_path.name} | {api_msg}", merged_item.get("upload_id")))
        self.refresh_admin_uploads(show_message=False)
        self.refresh_file_view_tree()
        self.refresh_history()
        messagebox.showinfo("PDF zusammenfassen", f"PDF wurde erstellt:\n{target_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")

    def image_to_pdf_file(self, image_path: Path, pdf_path: Path) -> None:
        """Wandelt eine einzelne Bilddatei in eine PDF-Datei um."""
        img = Image.open(image_path)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(pdf_path, "PDF", resolution=300.0)

    def document_create_payload_from_item(self, item: dict) -> dict:
        return {
            "upload_id": item.get("upload_id"),
            "original_filename": item.get("original_filename") or item.get("current_filename") or "",
            "stored_filename": item.get("stored_filename") or item.get("current_filename") or "",
            "current_filename": item.get("current_filename") or item.get("stored_filename") or "",
            "target_folder": item.get("target_folder") or "",
            "current_path": item.get("current_path") or "",
            "uploaded_at": str(item.get("uploaded_at") or datetime.now().isoformat(timespec="seconds")).replace("T", " "),
            "status": item.get("status") or ("erfasst" if item.get("odv_capture_mode") == "existing_file_metadata" else "hochgeladen"),
            "person_status": item.get("person_status") or "none",
            "import_uploaded_by_user_id": item.get("import_uploaded_by_user_id") or "",
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "archived_from_path": item.get("archived_from_path", ""),
            "metadata": {
                "document_type": item.get("document_type", ""),
                "primary_source": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "primaerquelle": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "secondary_source": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "sekundaerquelle": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "source": item.get("secondary_source", item.get("source", "")),
                "quelle": item.get("secondary_source", item.get("source", "")),
                "original_location": item.get("original_location", ""),
                "standort_original": item.get("original_location", ""),
                "document_date": item.get("document_date", ""),
                "datum": item.get("document_date", ""),
                "event": item.get("event", ""),
                "ereignis": item.get("event", ""),
                "place": item.get("place", ""),
                "ort": item.get("place", ""),
                "description": item.get("description", ""),
                "beschreibung": item.get("description", ""),
                "note": item.get("note", ""),
                "bemerkung": item.get("note", ""),
                "copyright_author": item.get("copyright_author", ""),
                "urheber": item.get("copyright_author", ""),
                "rights_holder": item.get("rights_holder", ""),
                "rechteinhaber": item.get("rights_holder", ""),
                "usage_permission": item.get("usage_permission", ""),
                "nutzungsfreigabe": item.get("usage_permission", ""),
                "license_note": item.get("license_note", ""),
                "lizenz": item.get("license_note", ""),
                "rights_note": item.get("rights_note", ""),
                "rechte": item.get("rights_note", ""),
                "archive_name": item.get("archive_name", ""),
                "archiv": item.get("archive_name", ""),
                "archive_signature": item.get("archive_signature", ""),
                "signatur": item.get("archive_signature", ""),
                "archive_accessed_at": item.get("archive_accessed_at", ""),
                "abruf_am": item.get("archive_accessed_at", ""),
                "keywords": item.get("keywords", ""),
                "stichwoerter": item.get("keywords", ""),
                "transcription_done": item.get("transcription_done", ""),
                "transcription_type": item.get("transcription_type", ""),
                "transcription_note": item.get("transcription_note", ""),
            },
            "persons": item.get("persons", []) or [],
        }

    def create_pdf_metadata_item(self, source_path: Path, pdf_path: Path, source_item: dict | None) -> dict:
        display_name = self.display_name_var.get().strip() or "Benutzer"
        item = dict(source_item or {})
        item.pop("_metadata_file", None)
        item["upload_id"] = make_upload_id()
        item["original_filename"] = source_path.name
        item["stored_filename"] = pdf_path.name
        item["current_filename"] = pdf_path.name
        item["current_path"] = str(pdf_path)
        item["target_folder"] = str(pdf_path.parent)
        item["uploaded_by"] = display_name
        item["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
        item["status"] = "hochgeladen"
        item["document_type"] = "PDF-Dokument"
        item["person_status"] = "none"
        item["persons"] = []
        item["source_image_path"] = str(source_path)
        item["history"] = []
        append_metadata_history(item, display_name, "PDF aus Bild erzeugt", f"{source_path} → {pdf_path}")
        return item

    def register_pdf_item(self, item: dict) -> tuple[bool, str, Path]:
        metadata_file = self.metadata_folder_path() / f"{item.get('upload_id')}.metadata.json"
        item["_metadata_file"] = str(metadata_file)
        save_metadata_file(metadata_file, item)
        api_ok, api_msg = False, "Kein API-Token vorhanden"
        if self.api_token:
            try:
                self.api.create_document(self.api_token, self.document_create_payload_from_item(item))
                api_ok, api_msg = True, "PDF-Metadaten wurden in MySQL gespeichert"
                append_metadata_history(item, self.display_name_var.get().strip() or "Benutzer", "MySQL gespeichert", api_msg)
                save_metadata_file(metadata_file, item)
            except ApiError as exc:
                api_msg = str(exc)
                append_metadata_history(item, self.display_name_var.get().strip() or "Benutzer", "MySQL nicht gespeichert", api_msg)
                save_metadata_file(metadata_file, item)
        return api_ok, api_msg, metadata_file

    def ask_delete_source_image(self, source_path: Path) -> None:
        if not source_path.exists():
            return
        if messagebox.askyesno("Bilddatei löschen?", "Die PDF-Datei wurde erzeugt.\n\nSoll die ursprüngliche Bilddatei gelöscht werden?\n\n" + str(source_path)):
            try:
                source_path.unlink()
                add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Benutzer", "Bilddatei gelöscht", str(source_path), None))
                app_log("info", "Bilddatei nach PDF-Umwandlung gelöscht", path=str(source_path))
            except Exception as exc:
                app_log_exception("Bilddatei konnte nicht gelöscht werden", exc, path=str(source_path))
                messagebox.showerror("Löschen fehlgeschlagen", f"Die Bilddatei konnte nicht gelöscht werden:\n{source_path}\n\n{exc}")

    def convert_file_view_image_to_pdf(self, path: Path | None = None) -> None:
        path = path or self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            messagebox.showwarning("Keine Bilddatei", "Bitte eine Bilddatei auswählen.")
            return
        default_pdf = unique_path_with_counter(path.with_suffix(".pdf"))
        target = filedialog.asksaveasfilename(
            title="Als PDF speichern",
            initialdir=str(path.parent),
            initialfile=default_pdf.name,
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf")],
        )
        if not target:
            return
        pdf_path = Path(target)
        try:
            self.image_to_pdf_file(path, pdf_path)
        except Exception as exc:
            app_log_exception("Bild konnte nicht in PDF umgewandelt werden", exc, path=str(path))
            messagebox.showerror("PDF erzeugen", f"PDF konnte nicht erstellt werden:\n{exc}")
            return
        source_item = self.file_view_current_metadata or {}
        item = self.create_pdf_metadata_item(path, pdf_path, source_item)
        api_ok, api_msg, metadata_file = self.register_pdf_item(item)
        self.file_view_metadata_items.append(item)
        self.file_view_metadata_by_path[str(pdf_path)] = item
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Benutzer", "PDF aus Bild erzeugt", f"{path.name} → {pdf_path.name} | {api_msg}", item.get("upload_id")))
        messagebox.showinfo("PDF erzeugt", f"PDF wurde erstellt:\n{pdf_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")
        self.ask_delete_source_image(path)
        self.refresh_file_view_tree()
        self.refresh_admin_uploads(show_message=False)
        self.refresh_history()

    def convert_admin_image_to_pdf(self, item: dict | None = None) -> None:
        if not self.require_admin():
            return
        item = item or self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            messagebox.showwarning("Keine Bilddatei", "Bitte eine Bilddatei auswählen.")
            return
        pdf_path = unique_path_with_counter(path.with_suffix(".pdf"))
        try:
            self.image_to_pdf_file(path, pdf_path)
        except Exception as exc:
            app_log_exception("Admin: Bild konnte nicht in PDF umgewandelt werden", exc, path=str(path))
            messagebox.showerror("PDF erzeugen", f"PDF konnte nicht erstellt werden:\n{exc}")
            return
        pdf_item = self.create_pdf_metadata_item(path, pdf_path, item)
        api_ok, api_msg, metadata_file = self.register_pdf_item(pdf_item)
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "PDF aus Bild erzeugt", f"{path.name} → {pdf_path.name} | {api_msg}", pdf_item.get("upload_id")))
        messagebox.showinfo("PDF erzeugt", f"PDF wurde erstellt:\n{pdf_path}\n\nMetadaten:\n{metadata_file}\n\n{api_msg}")
        self.ask_delete_source_image(path)
        self.refresh_admin_uploads(show_message=False)
        self.refresh_file_view_tree()
        self.refresh_history()

    def open_document_access_log_dialog(self) -> None:
        if not self.require_admin():
            return
        if not self.api_token:
            messagebox.showwarning("Dokumentzugriffe", "Keine API-Anmeldung vorhanden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Dokumentzugriffe")
        try: self.track_window_geometry(dialog, "Dokumentzugriffe")
        except Exception: pass
        dialog.geometry("1100x600")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Protokolliert werden Öffnen und Download/Kopie über die ODV-App.").pack(side="left")
        cols = ("created_at", "user", "action", "filename", "upload_id", "details")
        tree = ttk.Treeview(dialog, columns=cols, show="headings")
        headings = {
            "created_at": ("Zeitpunkt", 150),
            "user": ("Benutzer", 180),
            "action": ("Aktion", 120),
            "filename": ("Datei", 220),
            "upload_id": ("Upload-ID", 190),
            "details": ("Details", 300),
        }
        for c, (label, width) in headings.items():
            tree.heading(c, text=label)
            tree.column(c, width=width, anchor="w")
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        vsb.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        def load():
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.document_access_log(self.api_token, limit=500)
                rows = resp.get("entries") or resp.get("history") or []
                for row in rows:
                    action = str(row.get("action") or "")
                    action_label = {"document_opened": "geöffnet", "document_downloaded": "Download"}.get(action, action)
                    tree.insert("", "end", values=(
                        row.get("created_at", ""),
                        row.get("user_display_name", ""),
                        action_label,
                        row.get("current_filename") or row.get("filename") or "",
                        row.get("upload_id", ""),
                        row.get("details", ""),
                    ))
            except Exception as exc:
                messagebox.showerror("Dokumentzugriffe", f"Zugriffsliste konnte nicht geladen werden:\n{exc}")
        btns = ttk.Frame(dialog, padding=(8, 0, 8, 8))
        btns.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(btns, text="Aktualisieren", command=load).pack(side="left")
        ttk.Button(btns, text="Schließen", command=dialog.destroy).pack(side="right")
        load()

    def check_missing_place_folders(self) -> list[tuple[str, str, str]]:
        """Prüft Ortsordner-Stammdaten gegen den lokalen Nextcloud-Stammordner."""
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        missing: list[tuple[str, str, str]] = []
        if not base or not base.exists():
            return missing
        for place_norm, folder in sorted((self.place_folder_map or {}).items(), key=lambda x: str(x[1]).lower()):
            folder_text = str(folder or "").strip()
            if not folder_text:
                continue
            p = base / folder_text
            place_label = place_norm
            try:
                # Anzeige schöner: aus Stammdaten den normalisierten Ort wieder nutzen, wenn bekannt.
                for k, v in (self.place_folder_map or {}).items():
                    if v == folder:
                        place_label = k
                        break
            except Exception:
                pass
            if not p.exists() or not p.is_dir():
                missing.append((str(place_label), folder_text, str(p)))
        return missing

    def startup_system_check_lines(self) -> list[str]:
        """Kurze Systemprüfung für Startfenster und Superadmin-Kontrolle."""
        lines: list[str] = []
        try:
            status = self.api.status()
            api_version = str(status.get("api_version") or status.get("version") or "?")
            lines.append(f"API erreichbar: ja ({api_version})")
            if api_version != "?" and api_version != APP_VERSION:
                lines.append(f"Server-Version passend: nein – App {APP_VERSION}, API {api_version}")
            else:
                lines.append("Server-Version passend: ja")
            maintenance = status.get("maintenance") or {}
            if maintenance.get("active"):
                lines.append("Wartungsmodus: aktiv")
            elif maintenance.get("scheduled"):
                starts = maintenance.get("starts_at") or "geplant"
                lines.append(f"Wartungsmodus: geplant ab {starts}")
            else:
                lines.append("Wartungsmodus: nicht aktiv")
        except Exception as exc:
            lines.append(f"API erreichbar: nein ({exc})")
        try:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            lines.append(f"Nextcloud-Stammverzeichnis vorhanden: {'ja' if base.exists() and base.is_dir() else 'nein'}")
            lines.append(f"Lokaler Pfad: {base if str(base) else 'nicht gesetzt'}")
        except Exception as exc:
            lines.append(f"Nextcloud-Prüfung: Fehler ({exc})")
        try:
            if self.api_token:
                self.api.me(self.api_token)
                lines.append("Benutzer/Token gültig: ja")
            else:
                lines.append("Benutzer/Token gültig: nein")
        except Exception as exc:
            lines.append(f"Benutzer/Token gültig: nein ({exc})")
        if self.current_role() == "Superadmin" and self.api_token:
            try:
                b = self.api.backup_status(self.api_token)
                latest = b.get("latest") or {}
                if latest:
                    age = b.get("age_hours")
                    warn = " – WARNUNG: älter als 48 Stunden" if b.get("warning") else ""
                    lines.append(f"Letzte Datenbanksicherung: {latest.get('created_at','?')} · {latest.get('file','?')} · {latest.get('size_human','')}{warn}")
                else:
                    lines.append("Letzte Datenbanksicherung: keine gefunden")
            except Exception as exc:
                lines.append(f"Backup-Status: nicht abrufbar ({exc})")
            try:
                migrations = self.api.schema_migrations(self.api_token)
                pending = int(migrations.get("pending_count") or 0)
                lines.append(f"Datenbankmigrationen offen: {pending}")
            except Exception as exc:
                lines.append(f"Datenbankmigrationen: nicht abrufbar ({exc})")
        try:
            update = self.get_app_update_info()
            if update:
                latest_version = str(update.get("version") or "").strip()
                if latest_version:
                    status = "verfügbar" if self.is_newer_version(latest_version, APP_VERSION) else "nicht neuer"
                    req = " · Pflichtupdate" if update.get("required") else ""
                    lines.append(f"ODV-Update: {latest_version} ({status}){req}")
        except Exception as exc:
            lines.append(f"ODV-Updateprüfung: nicht abrufbar ({exc})")
        try:
            missing = self.check_missing_place_folders()
            if missing:
                lines.append("Ortsordner-Prüfung: Warnung")
                for place, folder, full in missing[:10]:
                    lines.append(f"- {place}: {full}")
                if len(missing) > 10:
                    lines.append(f"... weitere fehlende Ortsordner: {len(missing)-10}")
            else:
                lines.append("Ortsordner-Prüfung: ja")
        except Exception as exc:
            lines.append(f"Ortsordner-Prüfung: nicht möglich ({exc})")
        return lines

    def startup_action_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.current_role() != "Superadmin":
            return warnings
        api_version = "?"
        try:
            status = self.api.status()
            api_version = str(status.get("api_version") or status.get("version") or "?")
            if api_version != "?" and api_version != APP_VERSION:
                warnings.append(
                    f"Server-routes.php ist vermutlich nicht aktuell: App {APP_VERSION}, API {api_version}.\n"
                    "Bitte unter Admin > Server-routes.php sichern/hochladen... aktualisieren."
                )
        except Exception as exc:
            warnings.append(f"API-Status konnte nicht geprüft werden: {exc}")
            return warnings
        if api_version == APP_VERSION and self.api_token:
            try:
                migrations = self.api.schema_migrations(self.api_token)
                pending = int(migrations.get("pending_count") or 0)
                if pending > 0:
                    warnings.append(
                        f"Es gibt {pending} offene Datenbankmigration(en).\n"
                        "Bitte unter Admin > Datenbankmigrationen prüfen/ausführen... ausführen."
                    )
            except Exception as exc:
                warnings.append(f"Datenbankmigrationen konnten nicht geprüft werden: {exc}")
        return warnings

    def show_startup_action_warnings(self) -> None:
        try:
            warnings = self.startup_action_warnings()
            if not warnings:
                return
            messagebox.showwarning(
                "ODV-Handlungsbedarf",
                "\n\n".join(warnings),
                parent=self,
            )
        except Exception as exc:
            app_log_exception("Start-Hinweise konnten nicht geprüft werden", exc)

    def format_metadata_plain(self, item: dict) -> str:
        labels = {
            "upload_id": "Upload-ID",
            "original_filename": "Original-Dateiname",
            "stored_filename": "Gespeicherter Dateiname",
            "current_filename": "Aktueller Dateiname",
            "current_path": "Aktueller Pfad",
            "target_folder": "Zielordner",
            "uploaded_by": "Erfasst von",
            "uploaded_at": "Hochgeladen am",
            "status": "Status",
            "document_type": "Dokumenttyp",
            "primary_source": "Primärquelle",
            "secondary_source": "Sekundärquelle",
            "source": "Quelle",
            "original_location": "Standort Original",
            "document_date": "Datum / Zeitraum",
            "event": "Ereignis",
            "place": "Ort",
            "gps_coordinates": "GPS-Koordinaten",
            "gps_place": "GPS-Ort",
            "description": "Beschreibung",
            "note": "Bemerkung",
            "rights_note": "Rechte / Nutzung allgemein",
            "copyright_author": "Urheber/in",
            "rights_holder": "Rechteinhaber",
            "usage_permission": "Nutzungsfreigabe",
            "license_note": "Lizenz / Einschränkungen",
            "archive_name": "Archiv",
            "archive_signature": "Signatur",
            "archive_accessed_at": "Abruf am",
            "person_status": "Personenstatus",
            "persons": "Personen",
            "history": "Historie",
        }
        order = [
            "upload_id", "original_filename", "stored_filename", "current_filename", "current_path",
            "uploaded_by", "uploaded_at", "status", "document_type", "primary_source", "secondary_source", "source", "original_location",
            "document_date", "event", "place", "gps_coordinates", "gps_place", "copyright_author", "rights_holder",
            "usage_permission", "license_note", "archive_name", "archive_signature", "archive_accessed_at",
            "description", "note", "rights_note", "person_status", "persons", "history"
        ]
        lines: list[str] = []

        def add_value(label: str, value, indent: int = 0):
            prefix = "  " * indent
            if isinstance(value, list):
                lines.append(f"{prefix}{label}:")
                if not value:
                    lines.append(f"{prefix}  -")
                for i, entry in enumerate(value, 1):
                    if isinstance(entry, dict):
                        parts = []
                        if "timestamp" in entry:
                            parts.append(str(entry.get("timestamp", "")))
                        if "user_display_name" in entry:
                            parts.append(str(entry.get("user_display_name", "")))
                        if "action" in entry:
                            parts.append(str(entry.get("action", "")))
                        if "details" in entry:
                            parts.append(str(entry.get("details", "")))
                        if not parts:
                            parts = [f"{labels.get(k, k)}={v}" for k, v in entry.items()]
                        lines.append(f"{prefix}  {i}. " + " | ".join([p for p in parts if p]))
                    else:
                        lines.append(f"{prefix}  {i}. {entry}")
            elif isinstance(value, dict):
                lines.append(f"{prefix}{label}:")
                for k, v in value.items():
                    add_value(labels.get(k, k), v, indent + 1)
            else:
                text = "" if value is None else str(value)
                lines.append(f"{prefix}{label}: {text}")

        sections = [
            ("Technische Daten", ["upload_id", "original_filename", "stored_filename", "current_filename", "current_path", "target_folder", "status", "document_type"]),
            ("Upload / Bearbeitung", ["uploaded_by", "uploaded_at"]),
            ("Quelle / Herkunft", ["primary_source", "secondary_source", "source", "original_location"]),
            ("Zeit / Ort / Inhalt", ["document_date", "event", "place", "gps_coordinates", "gps_place", "description", "note"]),
            ("Rechte", ["copyright_author", "rights_holder", "usage_permission", "license_note", "rights_note"]),
            ("Archivdaten", ["archive_name", "archive_signature", "archive_accessed_at"]),
            ("Personen", ["person_status", "persons"]),
            ("Historie", ["history"]),
        ]
        seen = set()
        for heading, keys in sections:
            existing = [key for key in keys if key in item]
            if not existing:
                continue
            if lines:
                lines.append("")
            lines.append(heading)
            lines.append("-" * len(heading))
            for key in existing:
                add_value(labels.get(key, key), item.get(key))
                seen.add(key)
        rest = sorted(k for k in item.keys() if k not in seen)
        if rest:
            if lines:
                lines.append("")
            lines.append("Weitere Daten")
            lines.append("------------")
            for key in rest:
                add_value(labels.get(key, key), item.get(key))
        return "\n".join(lines)

    def draw_person_overlays(self, img: Image.Image, persons: list, show_persons: bool = True, font_size: int = 14) -> tuple[Image.Image, list[str]]:
        legend_lines: list[str] = []
        if not show_persons or not persons:
            return img, legend_lines
        draw = ImageDraw.Draw(img)
        w, h = img.size
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        for person in persons:
            try:
                x = float(person.get("x", 0)) * w
                y = float(person.get("y", 0)) * h
                number = str(person.get("number", "?"))
                name = str(person.get("name") or person.get("display_name") or "unbekannt")
                note = str(person.get("note") or "")
                certainty = str(person.get("certainty") or "")
                extra = ", ".join([v for v in [certainty, note] if v])
                legend_lines.append(f"{number}: {name}" + (f" ({extra})" if extra else ""))
                r = max(12, int(font_size * 0.9))
                draw.ellipse((x-r, y-r, x+r, y+r), fill="white", outline="red", width=2)
                bbox = draw.textbbox((0, 0), number, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((x - tw / 2, y - th / 2 - 1), number, fill="red", font=font)
            except Exception:
                continue
        return img, legend_lines

    def open_large_preview_window(self, path: Path, metadata: dict | None, title: str) -> None:
        if not path or not path.exists() or not is_image_file(path):
            return
        dialog = tk.Toplevel(self)
        dialog.title(title)
        try: self.track_window_geometry(dialog, title)
        except Exception: pass
        dialog.geometry("1100x800")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        show_var = tk.BooleanVar(value=True)
        top = ttk.Frame(dialog)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Checkbutton(top, text="Personen anzeigen", variable=show_var, command=lambda: render()).pack(side="left")
        label = ttk.Label(dialog, anchor="center")
        label.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        image_ref = {"img": None}
        persons = (metadata or {}).get("persons", []) or []
        def render():
            try:
                img = Image.open(path).convert("RGB")
                max_w = max(600, dialog.winfo_width() - 60)
                max_h = max(450, dialog.winfo_height() - 100)
                img.thumbnail((max_w, max_h))
                img, _legend = self.draw_person_overlays(img, persons, show_var.get(), font_size=18)
                image_ref["img"] = ImageTk.PhotoImage(img)
                label.configure(image=image_ref["img"], text="")
            except Exception as exc:
                label.configure(image="", text=f"Vorschaufehler:\n{exc}")
        dialog.bind("<Configure>", lambda _e: render())
        render()

    def open_large_file_preview(self) -> None:
        path = self.file_view_current_path
        if path and path.exists() and is_image_file(path):
            self.open_large_preview_window(path, self.file_view_current_metadata, path.name)

    def open_large_admin_preview(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if path and path.exists() and is_image_file(path):
            self.open_large_preview_window(path, item, path.name)

    def clear_file_view_selection(self) -> None:
        """Leert Dateiansicht, Vorschau und Metadaten, bis bewusst eine Datei ausgewählt wird."""
        self.file_view_current_path = None
        self.file_view_current_metadata = None
        try:
            self.file_tree.selection_remove(self.file_tree.selection())
        except Exception:
            pass
        if hasattr(self, "file_preview_label"):
            self.file_preview_image = None
            self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        if hasattr(self, "show_persons_check"):
            self.show_persons_check.grid_remove()
        if hasattr(self, "person_legend_frame"):
            self.person_legend_frame.grid_remove()
        if hasattr(self, "person_legend_text"):
            self.person_legend_text.configure(state="normal")
            self.person_legend_text.delete("1.0", "end")
            self.person_legend_text.configure(state="disabled")
        if hasattr(self, "file_view_write_hint_var"):
            self.file_view_write_hint_var.set("Keine Datei ausgewählt.")
        self.update_file_view_ocr_button()
        if hasattr(self, "file_view_meta_vars"):
            for var in self.file_view_meta_vars.values():
                try:
                    if isinstance(var, tk.BooleanVar):
                        var.set(False)
                    else:
                        var.set("")
                except Exception:
                    pass
        for attr in ("file_view_description_text", "file_view_note_text", "file_view_json_text"):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.configure(state="normal")
                    widget.delete("1.0", "end")
                    if attr == "file_view_json_text":
                        widget.insert("1.0", "Keine Datei ausgewählt.")
                        widget.configure(state="disabled")
                    else:
                        widget.configure(state="disabled")
                except Exception:
                    pass
        for widget in getattr(self, "file_view_meta_widgets", []):
            try:
                widget.configure(state="disabled")
            except Exception:
                pass

    def show_file_preview(self) -> None:
        path = self.file_view_current_path
        def set_legend(lines: list[str]):
            if hasattr(self, "person_legend_text"):
                self.person_legend_text.configure(state="normal")
                self.person_legend_text.delete("1.0", "end")
                self.person_legend_text.insert("1.0", "\n".join(lines) if lines else "")
                self.person_legend_text.configure(state="disabled")
        def hide_person_ui():
            if hasattr(self, "person_legend_frame"):
                self.person_legend_frame.grid_remove()
            if hasattr(self, "show_persons_check"):
                self.show_persons_check.grid_remove()
            set_legend([])
        if not path or not path.exists() or path.is_dir():
            self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
            hide_person_ui()
            return
        if not is_image_file(path):
            self.file_preview_label.configure(image="", text=f"Keine Bildvorschau für:\n{path.name}")
            hide_person_ui()
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
            set_legend(legend_lines if has_persons and self.show_persons_var.get() else [])
            self.file_preview_image = ImageTk.PhotoImage(img)
            self.file_preview_label.configure(image=self.file_preview_image, text="")
        except Exception as exc:
            self.file_preview_label.configure(image="", text=f"Vorschaufehler:\n{exc}")
            hide_person_ui()

    def load_file_view_metadata_form(self) -> None:
        path = self.file_view_current_path
        item = self.file_view_current_metadata or {}
        writable = self.can_edit_file_view_metadata(path, item)
        if writable:
            self.file_view_write_hint_var.set("Metadaten bearbeitbar" if item else "Datei noch nicht in ODV erfasst – Metadaten können angelegt werden")
        else:
            if item and item.get("upload_id") and not (str(item.get("uploaded_by_user_id") or item.get("user_id") or "").strip() or str(item.get("uploaded_by") or item.get("uploaded_by_name") or "").strip()) and not self.is_current_admin():
                self.file_view_write_hint_var.set("Nur Anzeige: kein Erfasser hinterlegt – Bearbeitung nur durch Admin/Superadmin")
            else:
                self.file_view_write_hint_var.set("Nur Anzeige: keine Bearbeitungsberechtigung für diese Datei")
        if hasattr(self, "file_view_uploaded_by_combo"):
            self.refresh_file_view_uploaded_by_options()
            if "uploaded_by" in self.file_view_meta_vars:
                uid = str(item.get("uploaded_by_user_id") or "")
                name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
                if not name and not item:
                    name = self.display_name_var.get().strip() or ""
                    uid = str(self.current_user.get("id", "") if getattr(self, "current_user", None) else "")
                label = next((lbl for lbl, u in getattr(self, "file_view_uploaded_by_user_map", {}).items() if str(u.get("id") or "") == uid), "")
                if not label:
                    label = next((lbl for lbl, u in getattr(self, "file_view_uploaded_by_user_map", {}).items() if str(u.get("display_name") or u.get("name") or "") == name), name)
                try:
                    self.file_view_meta_vars["uploaded_by"].set(label)
                except Exception:
                    pass
        for key, var in self.file_view_meta_vars.items():
            if key == "uploaded_by" and self.is_current_admin():
                continue
            value = item.get(key, "")
            if key == "document_type" and not value and path and path.is_file():
                value = detect_document_type(path)
            if key == "transcription_done" and isinstance(var, tk.BooleanVar):
                var.set(str(value).strip().lower() in {"1", "ja", "yes", "true", "x"})
            else:
                var.set(str(value or ""))
        try:
            self.file_view_description_text.configure(state="normal")
            self.file_view_note_text.configure(state="normal")
        except tk.TclError:
            pass
        self.file_view_description_text.delete("1.0", "end")
        self.file_view_description_text.insert("1.0", str(item.get("description", "") or ""))
        if getattr(self, "file_view_description_counter_var", None):
            self.update_description_counter(self.file_view_description_text, self.file_view_description_counter_var)
        self.file_view_note_text.delete("1.0", "end")
        self.file_view_note_text.insert("1.0", str(item.get("note", "") or ""))
        state = "normal" if writable else "disabled"
        for widget in getattr(self, "file_view_meta_widgets", []):
            try:
                if widget is getattr(self, "file_view_uploaded_by_combo", None):
                    widget.configure(state=("readonly" if writable and self.is_current_admin() else "disabled"))
                elif isinstance(widget, ttk.Combobox) and str(widget.cget("state")) == "readonly":
                    widget.configure(state=("readonly" if writable else "disabled"))
                else:
                    widget.configure(state=state)
            except tk.TclError:
                pass
        if hasattr(self, "file_view_json_text"):
            self.file_view_json_text.configure(state="normal")
            self.file_view_json_text.delete("1.0", "end")
            if item:
                view_item = {k: v for k, v in item.items() if k != "_metadata_file"}
                self.file_view_json_text.insert("1.0", self.format_metadata_plain(view_item))
            else:
                self.file_view_json_text.insert("1.0", "Keine JSON-Metadaten vorhanden. Beim Speichern werden neue Metadaten angelegt.")
            self.file_view_json_text.configure(state="disabled")
        self.update_file_view_ocr_button()

    def ensure_file_view_metadata_item(self, path: Path) -> tuple[dict, Path]:
        """Liefert vorhandene Metadaten zur Datei oder bereitet einen neuen Datensatz vor.

        Wichtig: Für physisch vorhandene Dateien ohne ODV-Metadaten wird hier noch
        nichts gespeichert. Erst ein echter Speichervorgang mit geänderten Feldern
        legt JSON/MySQL-Daten an.
        """
        metadata_folder = self.metadata_folder_path()
        path_key = str(path)
        item = self.file_view_metadata_by_path.get(path_key)
        if item and item.get("_metadata_file"):
            return item, Path(str(item["_metadata_file"]))

        upload_id = make_upload_id()
        display_name = self.display_name_var.get().strip() or "Benutzer"
        item = {
            "upload_id": upload_id,
            "original_filename": path.name,
            "stored_filename": path.name,
            "current_filename": path.name,
            "current_path": str(path),
            "status": "erfasst",
            "odv_capture_mode": "existing_file_metadata",
            "odv_captured_by_admin": bool(self.is_current_admin()),
            "uploaded_by": display_name,
            "uploaded_by_name": display_name,
            "uploaded_by_user_id": str(self.current_user.get("id", "") if getattr(self, "current_user", None) else ""),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "target_folder": str(path.parent),
            "document_type": detect_document_type(path),
            "primary_source": "",
            "secondary_source": "",
            "source": "",
            "original_location": "",
            "document_date": "",
            "event": "",
            "place": self.place_var.get().strip(),
            "description": "",
            "note": "",
            "rights_note": "",
            "copyright_author": "",
            "rights_holder": "",
            "usage_permission": "",
            "license_note": "",
            "archive_name": "",
            "archive_signature": "",
            "archive_accessed_at": "",
            "person_status": "none",
            "persons": [],
            "history": [],
            "_pending_existing_file_metadata": True,
        }
        metadata_file = metadata_folder / f"{upload_id}.metadata.json"
        item["_metadata_file"] = str(metadata_file)
        return item, metadata_file

    def find_admin_deposit_folder(self) -> Path | None:
        """Sucht einen beschreibbaren Ablageordner für Kopien aus schreibgeschützten Bereichen."""
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        preferred_names = ["01_ABLAGE_ORTSCHRONIK", "01_Ablage_Ortschronik", "01_ablage_ortschronik"]
        configured = list(self.admin_work_folder_names)
        names = preferred_names + [n for n in configured if n not in preferred_names]
        for name in names:
            direct = base / name
            if direct.exists() and direct.is_dir() and is_writable_folder(direct):
                return direct
        try:
            for folder in base.rglob("*"):
                if not folder.is_dir():
                    continue
                if folder.name.lower() in {n.lower() for n in names} and is_writable_folder(folder):
                    return folder
        except OSError:
            return None
        return None

    def create_person_tagging_copy_for_admin(self, source_path: Path, source_item: dict, persons: list[PersonMark]) -> tuple[Path, Path, dict] | None:
        """Erstellt bei fehlenden Schreibrechten eine Kopie in 01_ABLAGE_ORTSCHRONIK und speichert dort die neue Personenzuordnung."""
        deposit_folder = self.find_admin_deposit_folder()
        if not deposit_folder:
            messagebox.showerror(
                "Kein Ablageordner gefunden",
                "Es wurde kein beschreibbarer Ordner 01_ABLAGE_ORTSCHRONIK gefunden.\n"
                "Bitte den Nextcloud-Stammordner und die Admin-Einstellungen prüfen.",
            )
            return None

        upload_id = make_upload_id()
        if hasattr(self, "meta_vars"):
            if "upload_id" in self.meta_vars:
                self.meta_vars["upload_id"].set(upload_id)
            if "status" in self.meta_vars:
                self.meta_vars["status"].set("hochgeladen")
            if "uploaded_at" in self.meta_vars:
                self.meta_vars["uploaded_at"].set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_name = safe_filename(f"{timestamp}_personen_{source_path.name}")
        target_file = unique_path_with_counter(deposit_folder / target_name)
        try:
            shutil.copy2(source_path, target_file)
        except Exception as exc:
            messagebox.showerror("Kopie konnte nicht erstellt werden", str(exc))
            return None

        display_name = self.display_name_var.get().strip() or "Benutzer"
        new_item = dict(source_item or {})
        new_item.pop("_metadata_file", None)
        new_item["upload_id"] = upload_id
        new_item["original_filename"] = source_item.get("original_filename") or source_path.name
        new_item["stored_filename"] = target_file.name
        new_item["current_filename"] = target_file.name
        new_item["current_path"] = str(target_file)
        new_item["target_folder"] = str(deposit_folder)
        new_item["status"] = "hochgeladen"
        new_item["uploaded_by"] = display_name
        new_item["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
        new_item["document_type"] = new_item.get("document_type") or detect_document_type(source_path)
        new_item["source_copy_of_path"] = str(source_path)
        new_item["copy_reason"] = "Personenzuordnung aus schreibgeschütztem Ordner"
        new_item["persons"] = [p.to_dict() for p in persons]
        new_item["person_status"] = "identified" if persons else "none"
        new_item["history"] = []
        append_metadata_history(new_item, display_name, "Kopie erstellt", f"Aus schreibgeschütztem Ordner: {source_path}")
        append_metadata_history(new_item, display_name, "Personenzuordnung geändert", f"{len(persons)} Personenmarkierungen")

        metadata_file = self.metadata_folder_path() / f"{upload_id}.metadata.json"
        save_metadata_file(metadata_file, new_item)
        new_item["_metadata_file"] = str(metadata_file)
        return target_file, metadata_file, new_item

    def edit_persons_for_current_file(self) -> None:
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not is_image_file(path):
            return
        source_item = self.file_view_current_metadata or {}
        tagger = PersonTagger(self, path, initial_persons=source_item.get("persons", []) or [])
        result = tagger.show_modal()
        if result is None:
            return

        display_name = self.display_name_var.get().strip() or "Benutzer"
        if is_writable_folder(path.parent):
            item, metadata_file = self.ensure_file_view_metadata_item(path)
            item["persons"] = [p.to_dict() for p in result]
            item["person_status"] = "identified" if result else "none"
            append_metadata_history(item, display_name, "Personenzuordnung geändert", f"{len(result)} Personenmarkierungen")
            save_metadata_file(metadata_file, item)
            item["_metadata_file"] = str(metadata_file)
            if self.api_token and item.get("upload_id"):
                try:
                    # Falls der Datensatz schon in MySQL existiert: Personen dort ebenfalls aktualisieren.
                    self.api.update_persons(self.api_token, str(item.get("upload_id")), item["persons"])
                except ApiError:
                    pass
            self.file_view_current_metadata = item
            add_history(HistoryEntry.now(display_name, "Personenzuordnung geändert", f"{path.name}: {len(result)} Personenmarkierungen", item.get("upload_id")))
            self.load_file_view_metadata_form()
            self.show_file_preview()
        else:
            if not messagebox.askyesno(
                "Keine Schreibberechtigung",
                "In diesem Ordner bestehen keine Schreibrechte.\n\n"
                "Soll eine Kopie mit der Personenzuordnung in 01_ABLAGE_ORTSCHRONIK abgelegt werden, "
                "damit ein Admin die Datei weiter bearbeiten kann?",
            ):
                return
            created = self.create_person_tagging_copy_for_admin(path, source_item, result)
            if not created:
                return
            target_file, metadata_file, new_item = created
            if self.api_token:
                try:
                    self.api.create_document(self.api_token, self.document_create_payload_from_item(new_item))
                    if new_item.get("persons"):
                        self.api.update_persons(self.api_token, str(new_item.get("upload_id")), new_item.get("persons", []))
                except ApiError as exc:
                    append_metadata_history(new_item, display_name, "MySQL nicht gespeichert", str(exc))
                    save_metadata_file(metadata_file, new_item)
            self.file_view_metadata_items.append(new_item)
            self.file_view_metadata_by_path[str(target_file)] = new_item
            add_history(HistoryEntry.now(display_name, "Kopie für Admin-Bearbeitung erstellt", f"{path.name} → {target_file}; {len(result)} Personenmarkierungen", new_item.get("upload_id")))
            messagebox.showinfo(
                "Kopie erstellt",
                "Die Personenzuordnung wurde nicht am Original gespeichert.\n\n"
                f"Kopie für Admin-Bearbeitung:\n{target_file}\n\n"
                f"Metadaten:\n{metadata_file}",
            )
            self.refresh_file_view_tree()
            self.refresh_admin_uploads(show_message=False)
        self.refresh_history()

    def edit_persons_for_admin_file(self) -> None:
        if not self.require_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            return
        path_text = item.get("current_path") or ""
        path = Path(path_text) if path_text else None
        if not path or not path.exists() or not is_image_file(path):
            return
        if not is_writable_folder(path.parent):
            messagebox.showwarning("Keine Schreibberechtigung", "Personen können nur bearbeitet werden, wenn im Ordner Schreibrecht besteht.")
            return
        tagger = PersonTagger(self, path, initial_persons=item.get("persons", []) or [])
        result = tagger.show_modal()
        if result is None:
            return
        item["persons"] = [p.to_dict() for p in result]
        item["person_status"] = "identified" if result else "none"
        display_name = self.display_name_var.get().strip() or "Admin"
        append_metadata_history(item, display_name, "Personenzuordnung geändert", f"{len(result)} Personenmarkierungen")
        api_msg = ""
        if self.api_token and item.get("upload_id"):
            try:
                self.api.update_persons(self.api_token, str(item.get("upload_id")), item["persons"])
                api_msg = "MySQL-Personen aktualisiert"
            except ApiError as exc:
                api_msg = f"MySQL nicht aktualisiert: {exc}"
                messagebox.showwarning("API", api_msg)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Personenzuordnung geändert", f"{path.name}: {len(result)} Personenmarkierungen | {api_msg}", item.get("upload_id")))
        self.show_selected_admin_details()
        self.refresh_history()

    def save_file_view_metadata(self, auto: bool = False) -> None:
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir():
            return
        writable = self.can_edit_file_view_metadata(path, self.file_view_current_metadata)
        if not writable:
            if not auto:
                messagebox.showwarning("Keine Berechtigung", "Metadaten können nur mit Schreibrecht auf den Ordner, bei eigenen Dateien oder durch Admin/Superadmin geändert werden. Bei fehlendem Erfasser reicht Schreibrecht auf den Ordner; sonst nur Admin/Superadmin.")
            return
        item, metadata_file = self.ensure_file_view_metadata_item(path)
        changed = []
        for key, var in self.file_view_meta_vars.items():
            if key == "uploaded_by" and self.is_current_admin():
                continue
            old = str(item.get(key, "") or "")
            raw_value = var.get()
            new = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
            if old != new:
                item[key] = new
                changed.append(key)
        for key, widget in [("description", self.file_view_description_text), ("note", self.file_view_note_text)]:
            old = str(item.get(key, "") or "")
            new = widget.get("1.0", "end").strip()
            if old != new:
                item[key] = new
                changed.append(key)
        if not changed:
            return
        display_name = self.display_name_var.get().strip() or "Benutzer"
        is_new_existing_file = bool(item.pop("_pending_existing_file_metadata", False))
        if is_new_existing_file:
            append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV erfasst", f"Dateiansicht: {path.name}; Felder: {', '.join(changed)}")
        else:
            append_metadata_history(item, display_name, "Metadaten geändert", f"Dateiansicht: {path.name}; Felder: {', '.join(changed)}")
        api_ok, api_msg = self.save_file_view_item_to_storage(item, metadata_file, is_new_existing_file)
        if not api_ok:
            app_log("warning", "Dateiansicht-Metadaten nur lokal gespeichert", upload_id=item.get("upload_id"), message=api_msg)
        if hasattr(self, "file_view_json_text"):
            self.file_view_json_text.configure(state="normal")
            self.file_view_json_text.delete("1.0", "end")
            self.file_view_json_text.insert("1.0", self.format_metadata_plain({k: v for k, v in item.items() if k != "_metadata_file"}))
            self.file_view_json_text.configure(state="disabled")
        add_history(HistoryEntry.now(display_name, "Metadaten geändert", f"{path.name}: {', '.join(changed)}", item.get("upload_id")))
        self.refresh_history()
        if not auto:
            messagebox.showinfo("Metadaten", "Metadaten wurden gespeichert.")


    def load_active_user_options(self) -> tuple[list[str], dict[str, dict]]:
        """Lädt aktive Benutzer für Auswahlfelder; Rückgabe: Labels und Label->User."""
        labels: list[str] = []
        mapping: dict[str, dict] = {}
        if not self.api_token:
            return labels, mapping
        try:
            resp = self.api.list_users(self.api_token)
            for u in resp.get("users", []) or []:
                try:
                    if int(u.get("is_active", u.get("active", 1)) or 0) != 1:
                        continue
                except Exception:
                    pass
                label = f"{u.get('display_name') or u.get('name') or u.get('username')} ({u.get('username') or u.get('id')})"
                labels.append(label)
                mapping[label] = u
        except Exception as exc:
            app_log_exception("Benutzerliste für Auswahl konnte nicht geladen werden", exc)
        return labels, mapping

    def refresh_admin_uploaded_by_options(self) -> None:
        if not hasattr(self, "admin_uploaded_by_combo"):
            return
        labels, mapping = self.load_active_user_options()
        self.admin_uploaded_by_user_map = mapping
        try:
            self.admin_uploaded_by_combo.configure(values=labels)
        except Exception:
            pass

    def refresh_file_view_uploaded_by_options(self) -> None:
        if not hasattr(self, "file_view_uploaded_by_combo"):
            return
        labels, mapping = self.load_active_user_options()
        self.file_view_uploaded_by_user_map = mapping
        try:
            self.file_view_uploaded_by_combo.configure(values=labels)
        except Exception:
            pass

    def save_file_view_item_to_storage(self, item: dict, metadata_file: Path, is_new_existing_file: bool) -> tuple[bool, str]:
        """Speichert ein Dateiansicht-Item als JSON und über die API.

        Bei vorhandenen Dateien ohne ODV-Datensatz wird erst hier bewusst ein
        Dokument erzeugt. Nur Anzeigen, Vorschau oder Doppelklick bleiben ohne
        DB-Schreibzugriff.
        """
        if is_new_existing_file:
            item.pop("_pending_existing_file_metadata", None)
        save_metadata_file(metadata_file, item)
        item["_metadata_file"] = str(metadata_file)
        path_key = str(item.get("current_path") or "")
        if path_key and path_key not in self.file_view_metadata_by_path:
            self.file_view_metadata_by_path[path_key] = item
            self.file_view_metadata_items.append(item)
        if not (self.api_token and item.get("upload_id")):
            return False, "Kein API-Token oder keine Upload-ID vorhanden"
        try:
            if is_new_existing_file:
                self.api.create_document(self.api_token, self.item_create_payload_for_api(item))
                return True, "MySQL-Dokument angelegt"
            try:
                self.api.lock_document(self.api_token, str(item.get("upload_id")))
            except ApiError as lock_exc:
                return False, str(lock_exc)
            self.api.update_document(self.api_token, str(item.get("upload_id")), self.item_payload_for_api(item))
            return True, "MySQL aktualisiert"
        except ApiError as exc:
            app_log_exception("Dateiansicht-Metadaten konnten nicht in MySQL gespeichert werden", exc, upload_id=item.get("upload_id"))
            return False, str(exc)

    def file_view_uploaded_by_changed(self, _event=None) -> None:
        if not self.is_current_admin():
            return
        path = self.file_view_current_path
        if not path or not path.exists() or path.is_dir() or not self.can_edit_file_view_metadata(path, self.file_view_current_metadata):
            return
        label = self.file_view_meta_vars.get("uploaded_by").get() if hasattr(self, "file_view_meta_vars") and "uploaded_by" in self.file_view_meta_vars else ""
        user = getattr(self, "file_view_uploaded_by_user_map", {}).get(label)
        if not user:
            return
        item, metadata_file = self.ensure_file_view_metadata_item(path)
        old_name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
        old_id = str(item.get("uploaded_by_user_id") or "")
        new_id = str(user.get("id") or "")
        new_name = str(user.get("display_name") or user.get("name") or user.get("username") or "")
        if old_id == new_id and old_name == new_name:
            return
        is_new_existing_file = bool(item.get("_pending_existing_file_metadata", False))
        item["uploaded_by_user_id"] = new_id
        item["uploaded_by_name"] = new_name
        item["uploaded_by"] = new_name
        display_name = self.display_name_var.get().strip() or "Admin"
        if is_new_existing_file:
            append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV erfasst", f"Erfasst von: {new_name}")
        else:
            append_metadata_history(item, display_name, "Erfasst von geändert", f"{old_name} → {new_name}")
        api_ok, api_msg = self.save_file_view_item_to_storage(item, metadata_file, is_new_existing_file)
        if not api_ok:
            messagebox.showwarning("Erfasst von", api_msg)
            return
        self.file_view_current_metadata = item
        add_history(HistoryEntry.now(display_name, "Erfasst von geändert", f"{old_name} → {new_name}", item.get("upload_id")))
        self.load_file_view_metadata_form()
        self.refresh_history()

    def admin_uploaded_by_changed(self, _event=None) -> None:
        if not self.is_current_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            return
        label = self.admin_meta_vars.get("uploaded_by").get() if hasattr(self, "admin_meta_vars") and "uploaded_by" in self.admin_meta_vars else ""
        user = getattr(self, "admin_uploaded_by_user_map", {}).get(label)
        if not user:
            return
        old_name = str(item.get("uploaded_by") or item.get("uploaded_by_name") or "")
        old_id = str(item.get("uploaded_by_user_id") or "")
        new_id = str(user.get("id") or "")
        new_name = str(user.get("display_name") or user.get("name") or user.get("username") or "")
        if old_id == new_id and old_name == new_name:
            return
        item["uploaded_by_user_id"] = new_id
        item["uploaded_by_name"] = new_name
        item["uploaded_by"] = new_name
        api_ok, api_msg = self.save_item_to_api(item)
        if not api_ok:
            messagebox.showwarning("Erfasst von", api_msg)
            return
        add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Admin", "Erfasst von geändert", f"{old_name} → {new_name}", item.get("upload_id")))
        self.refresh_admin_uploads(show_message=False)
        try:
            self.admin_tree.selection_set(str(item.get("upload_id")))
        except Exception:
            pass
        self.show_selected_admin_details()

    def open_document_in_admin_by_upload_id(self, upload_id: str) -> None:
        if not upload_id:
            return
        try:
            self.notebook.select(self.admin_tab)
        except Exception:
            pass
        self.refresh_admin_uploads(show_message=False)
        try:
            self.admin_tree.selection_set(upload_id)
            self.admin_tree.see(upload_id)
            self.show_selected_admin_details()
        except Exception:
            messagebox.showwarning("Dokument öffnen", "Das Dokument ist in der aktuellen Bearbeitungsliste nicht sichtbar.")

    def create_admin_tab(self) -> None:
        self.admin_tab.columnconfigure(0, weight=1)
        self.admin_tab.rowconfigure(0, weight=1)

        self.admin_outer_pane = ttk.PanedWindow(self.admin_tab, orient=tk.HORIZONTAL)
        self.admin_outer_pane.grid(row=0, column=0, sticky="nsew")
        self.admin_outer_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())

        list_frame = ttk.LabelFrame(self.admin_outer_pane, text="Uploads / Dateien", padding=8)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        filter_frame = ttk.Frame(list_frame)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(filter_frame, text="Status:").pack(side="left")
        self.admin_status_var = tk.StringVar(value="alle")
        self.admin_status_combo = ttk.Combobox(filter_frame, textvariable=self.admin_status_var, values=["alle", "hochgeladen", "erfasst", "in_pruefung", "rueckfrage", "uebernommen", "abgelehnt", "archiviert", "geloescht"], width=18, state="readonly")
        self.admin_status_combo.pack(side="left", padx=4)
        self.admin_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_admin_uploads(show_message=False))
        self.merge_pdfs_top_button = ttk.Button(filter_frame, text="Ausgewählte PDFs zusammenfassen...", command=self.merge_selected_admin_pdfs)
        self.merge_pdfs_top_button.pack(side="left", padx=(16, 0))

        self.admin_tree = ttk.Treeview(
            list_frame,
            columns=("upload_id", "status", "filename", "by", "date", "type"),
            show="headings",
            selectmode="extended",
        )
        for col, label, width in [
            ("upload_id", "Upload-ID", 155),
            ("status", "Status", 100),
            ("filename", "Datei", 270),
            ("by", "Erfasst von", 160),
            ("date", "Datum", 150),
            ("type", "Typ", 130),
        ]:
            self.admin_tree.heading(col, text=label, anchor="w")
            self.admin_tree.column(col, width=width, anchor="w")
        self.admin_tree.grid(row=1, column=0, sticky="nsew")
        self.admin_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_selected_admin_details())
        self.admin_tree.bind("<Double-1>", lambda _e: self.open_selected_admin_file())
        self.admin_tree.bind("<Button-3>", self.show_admin_tree_context_menu)
        admin_vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.admin_tree.yview)
        admin_hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.admin_tree.xview)
        self.admin_tree.configure(yscrollcommand=admin_vsb.set, xscrollcommand=admin_hsb.set)
        admin_vsb.grid(row=1, column=1, sticky="ns")
        admin_hsb.grid(row=2, column=0, sticky="ew")

        actions = ttk.LabelFrame(list_frame, text="Admin-Aktionen", padding=8)
        self.admin_actions_frame = actions
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(1, weight=1)
        self.new_status_label = ttk.Label(actions, text="Dokumentstatus:")
        self.new_status_label.grid(row=0, column=0, sticky="w")
        self.new_status_var = tk.StringVar(value="in_pruefung")
        self.new_status_combo = ttk.Combobox(actions, textvariable=self.new_status_var, values=["hochgeladen", "erfasst", "in_pruefung", "rueckfrage", "uebernommen", "abgelehnt", "archiviert", "geloescht"], width=18, state="readonly")
        self.new_status_combo.grid(row=0, column=1, sticky="w", padx=6)
        self.new_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.admin_set_status(silent=True))

        self.admin_destination_label = ttk.Label(actions, text="Datei ablegen in:")
        self.admin_destination_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.admin_destination_var = tk.StringVar()
        self.admin_destination_combo = ttk.Combobox(actions, textvariable=self.admin_destination_var, state="readonly")
        self.admin_destination_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.admin_destination_tree_button = ttk.Button(actions, text="Baum...", command=self.choose_admin_destination)
        self.admin_destination_tree_button.grid(row=1, column=2, sticky="e", padx=6, pady=(6, 0))

        ttk.Label(actions, text="Neuer Dateiname:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.admin_new_filename_var = tk.StringVar()
        ttk.Entry(actions, textvariable=self.admin_new_filename_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.admin_rename_button = ttk.Button(actions, text="Datei umbenennen / verschieben", command=self.admin_rename_or_move)
        self.admin_rename_button.grid(row=2, column=2, sticky="e", padx=6, pady=(6, 0))
        points_frame = ttk.Frame(actions)
        points_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Label(points_frame, text="Punkte Dokument:").pack(side="left")
        self.admin_document_points_var = tk.StringVar(value="keine Datei ausgewählt")
        ttk.Label(points_frame, textvariable=self.admin_document_points_var).pack(side="left", padx=(6, 18))
        self.manual_points_button = ttk.Button(points_frame, text="Sonderpunkte erfassen...", command=self.open_manual_points_dialog)
        self.manual_points_button.pack(side="left", padx=(0, 8))
        self.point_details_button = ttk.Button(points_frame, text="Punktdetails...", command=self.open_document_points_detail_dialog)
        self.point_details_button.pack(side="left")

        self.admin_right_pane = ttk.PanedWindow(self.admin_outer_pane, orient=tk.VERTICAL)
        self.admin_right_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())
        self.admin_outer_pane.add(list_frame, weight=1)
        self.admin_outer_pane.add(self.admin_right_pane, weight=2)
        self.configure_admin_actions_for_role()

        admin_preview_frame = ttk.LabelFrame(self.admin_right_pane, text="Vorschau / Personen", padding=8)
        self.admin_preview_frame = admin_preview_frame
        admin_preview_frame.columnconfigure(0, weight=0)
        admin_preview_frame.columnconfigure(1, weight=1)
        admin_preview_frame.rowconfigure(1, weight=1)
        self.admin_show_persons_var = tk.BooleanVar(value=True)
        self.admin_show_persons_check = ttk.Checkbutton(admin_preview_frame, text="Personen anzeigen", variable=self.admin_show_persons_var, command=lambda: self.show_admin_preview(self.selected_admin_upload() or {}))
        self.admin_show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.admin_show_persons_check.grid_remove()
        self.admin_person_legend_text, admin_legend_frame = self.make_scrolled_text(admin_preview_frame, height=7, wrap="word")
        self.admin_person_legend_frame = admin_legend_frame
        admin_legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.admin_person_legend_text.configure(width=30, state="disabled")
        self.admin_preview_label = ttk.Label(admin_preview_frame, text="Keine Datei ausgewählt.", anchor="center")
        self.admin_preview_label.grid(row=1, column=1, sticky="nsew")
        self.admin_preview_label.bind("<Double-1>", lambda _e: self.edit_persons_for_admin_file())
        self.admin_preview_image = None

        detail_outer = ttk.LabelFrame(self.admin_right_pane, text="Metadaten bearbeiten", padding=8)
        detail_outer.columnconfigure(0, weight=1)
        detail_outer.rowconfigure(0, weight=1)
        detail_canvas = tk.Canvas(detail_outer, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(detail_outer, orient="vertical", command=detail_canvas.yview)
        detail_frame = ttk.Frame(detail_canvas)
        detail_window = detail_canvas.create_window((0, 0), window=detail_frame, anchor="nw")
        detail_frame.bind("<Configure>", lambda _e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))
        detail_canvas.bind("<Configure>", lambda e: detail_canvas.itemconfigure(detail_window, width=e.width))
        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_canvas.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")

        form = self.create_metadata_form_two_columns(detail_frame, "admin")
        self.admin_meta_vars = form["vars"]  # type: ignore[assignment]
        self.admin_meta_widgets = form.get("widgets", [])  # type: ignore[assignment]
        self.admin_description_text = form["description_text"]  # type: ignore[assignment]
        self.admin_description_counter_var = form.get("description_counter_var")  # type: ignore[assignment]
        self.admin_note_text = form["note_text"]  # type: ignore[assignment]
        self.admin_json_text = form["json_text"]  # type: ignore[assignment]
        self.refresh_admin_uploaded_by_options()

        self.admin_right_pane.add(admin_preview_frame, weight=1)
        self.admin_right_pane.add(detail_outer, weight=3)
        self.refresh_admin_destination_choices()
        self.after(200, self.restore_pane_positions)

    def open_admin_settings_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Admin-Einstellungen sind nur für Superadmins sichtbar.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Admin-Einstellungen")
        try: self.track_window_geometry(dialog, "Admin-Einstellungen")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("920x720")
        dialog.minsize(880, 640)
        dialog.resizable(True, True)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Admin-Einstellungen", font=("", 12, "bold")).grid(row=0, column=0, sticky="w")

        dirty_var = tk.BooleanVar(value=False)
        saving_var = tk.BooleanVar(value=False)

        def mark_dirty(*_args) -> None:
            if not saving_var.get():
                dirty_var.set(True)

        notebook = ttk.Notebook(dialog)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        general_tab = ttk.Frame(notebook, padding=12)
        api_tab = ttk.Frame(notebook, padding=12)
        ftp_tab = ttk.Frame(notebook, padding=12)
        links_tab = ttk.Frame(notebook, padding=12)
        notebook.add(general_tab, text="Allgemein")
        notebook.add(api_tab, text="API / OpenAI")
        notebook.add(ftp_tab, text="FTP-Deployment")
        notebook.add(links_tab, text="Links / Hinweise")
        for tab in (general_tab, api_tab, ftp_tab, links_tab):
            tab.columnconfigure(1, weight=1)

        ttk.Label(general_tab, text="Metadaten und Arbeitsordner", font=("", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(general_tab, text="Metadatenordner unter Nextcloud-Stammverzeichnis:").grid(row=1, column=0, sticky="w", pady=6)
        folder_name_var = tk.StringVar(value=self.config_data.get("metadata_folder_name", ".ortschronik_metadaten"))
        ttk.Entry(general_tab, textvariable=folder_name_var, width=42).grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(general_tab, text="Beispiel: .ortschronik_metadaten").grid(row=1, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(general_tab, text="Aktueller vollständiger Metadatenpfad:").grid(row=2, column=0, sticky="w", pady=6)
        meta_preview_var = tk.StringVar(value=self.metadata_folder_var.get())
        ttk.Label(general_tab, textvariable=meta_preview_var).grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(general_tab, text="Ordner, die Admins bearbeiten dürfen:").grid(row=3, column=0, sticky="nw", pady=(10, 6))
        work_text = tk.Text(general_tab, height=8, width=55)
        work_text.grid(row=3, column=1, columnspan=2, sticky="nsew", padx=6, pady=(10, 6))
        work_text.insert("1.0", "\n".join(sorted(self.admin_work_folder_names)))
        work_text.bind("<<Modified>>", lambda _event: (work_text.edit_modified(False), mark_dirty()))
        general_tab.rowconfigure(3, weight=1)
        ttk.Label(general_tab, text="Ein Ordnername pro Zeile. Es reicht der Ordnername, z. B. 01_ABLAGE_ORTSCHRONIK.", wraplength=620).grid(row=4, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 10))

        ttk.Label(api_tab, text="Server / API", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(api_tab, text="API-URL:").grid(row=1, column=0, sticky="w", pady=4)
        api_url_var = tk.StringVar(value=self.config_data.get("api_url", "https://ortschronik.info/api"))
        ttk.Entry(api_tab, textvariable=api_url_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        ttk.Label(api_tab, text="MySQL-Host:").grid(row=2, column=0, sticky="w", pady=4)
        mysql_host_var = tk.StringVar(value=self.config_data.get("mysql_host", "https://ortschronik.info"))
        ttk.Entry(api_tab, textvariable=mysql_host_var).grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="Port:").grid(row=2, column=2, sticky="w", padx=6, pady=4)
        mysql_port_var = tk.StringVar(value=self.config_data.get("mysql_port", "3306"))
        ttk.Entry(api_tab, textvariable=mysql_port_var, width=8).grid(row=2, column=3, sticky="w", padx=6, pady=4)
        ttk.Label(api_tab, text="Datenbank:").grid(row=3, column=0, sticky="w", pady=4)
        mysql_database_var = tk.StringVar(value=self.config_data.get("mysql_database", "d047179a"))
        ttk.Entry(api_tab, textvariable=mysql_database_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="Datenbank-Benutzer:").grid(row=4, column=0, sticky="w", pady=4)
        mysql_user_var = tk.StringVar(value=self.config_data.get("mysql_user", "d047179a"))
        ttk.Entry(api_tab, textvariable=mysql_user_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        ttk.Separator(api_tab).grid(row=5, column=0, columnspan=4, sticky="ew", pady=(12, 10))
        ttk.Label(api_tab, text="OpenAI", font=("", 10, "bold")).grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(api_tab, text="OpenAI API-Schlüssel:").grid(row=7, column=0, sticky="w", pady=4)
        openai_key_var = tk.StringVar(value=self.config_data.get("openai_api_key", ""))
        ttk.Entry(api_tab, textvariable=openai_key_var, width=42, show="*").grid(row=7, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="OpenAI-Modell:").grid(row=8, column=0, sticky="w", pady=4)
        openai_model_var = tk.StringVar(value=self.config_data.get("openai_model", "gpt-3.5-turbo"))
        openai_model_values = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        if openai_model_var.get().strip() and openai_model_var.get().strip() not in openai_model_values:
            openai_model_values.append(openai_model_var.get().strip())
        ttk.Combobox(api_tab, textvariable=openai_model_var, values=openai_model_values, state="readonly").grid(row=8, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        openai_pdf_pages_var = tk.StringVar(value=str(self.config_data.get("openai_pdf_sample_pages", 10) or 10))
        openai_text_chars_var = tk.StringVar(value=str(self.config_data.get("openai_text_sample_chars", 4000) or 4000))
        openai_points_var = tk.StringVar(value=str(self.config_data.get("openai_metadata_points", 1) or 1))
        ttk.Label(api_tab, text="OpenAI-Auszug:").grid(row=9, column=0, sticky="w", pady=4)
        openai_limits_frame = ttk.Frame(api_tab)
        openai_limits_frame.grid(row=9, column=1, columnspan=3, sticky="w", padx=6, pady=4)
        ttk.Label(openai_limits_frame, text="PDF-Seiten").pack(side="left")
        ttk.Spinbox(openai_limits_frame, from_=1, to=100, textvariable=openai_pdf_pages_var, width=6).pack(side="left", padx=(6, 16))
        ttk.Label(openai_limits_frame, text="max. Zeichen").pack(side="left")
        ttk.Spinbox(openai_limits_frame, from_=500, to=100000, increment=500, textvariable=openai_text_chars_var, width=8).pack(side="left", padx=(6, 16))

        def reset_openai_limits() -> None:
            openai_pdf_pages_var.set("10")
            openai_text_chars_var.set("4000")
            openai_points_var.set("1")

        ttk.Button(openai_limits_frame, text="Standard", command=reset_openai_limits).pack(side="left")
        ttk.Label(openai_limits_frame, text="OpenAI-Punkte je Feld").pack(side="left", padx=(16, 0))
        ttk.Spinbox(openai_limits_frame, from_=0, to=50, textvariable=openai_points_var, width=6).pack(side="left", padx=(6, 0))
        ttk.Label(api_tab, text="Empfohlen: gpt-4o-mini. Für PDFs werden standardmäßig nur die ersten 10 Seiten und maximal 4000 Zeichen an OpenAI gegeben. OpenAI-Punkte werden je Metadatenfeld in der Punkteverwaltung gepflegt.", wraplength=760).grid(row=10, column=0, columnspan=4, sticky="w", pady=(0, 8))

        openai_test_status_var = tk.StringVar(value="OpenAI-Schlüssel nicht geprüft")
        openai_balance_var = tk.StringVar(value="Guthaben: n.v.")

        def load_openai_points_rule() -> None:
            if not self.api_token:
                return
            def run_load() -> None:
                try:
                    resp = self.api.list_point_rules(self.api_token, self._current_points_year())
                    for rule in resp.get("rules", []) or []:
                        if str(rule.get("evaluation_source", "")) == "openAI":
                            self.after(0, lambda value=str(int(rule.get("points", 1) or 0)): openai_points_var.set(value))
                            break
                except Exception:
                    pass
            threading.Thread(target=run_load, daemon=True).start()

        load_openai_points_rule()

        def check_openai_key() -> None:
            openai_test_status_var.set("OpenAI prüft …")
            openai_balance_var.set("Guthaben: n.v.")
            def run_check() -> None:
                try:
                    client = OpenAIClient(openai_key_var.get().strip(), openai_model_var.get().strip() or "gpt-3.5-turbo")
                    client.verify_key()
                    balance = client.get_balance()
                    available = balance.get("available")
                    if isinstance(available, (int, float)):
                        balance_text = f"Guthaben: {available:.2f} USD"
                    else:
                        balance_text = "Guthaben: k.A."
                    self.after(0, lambda: openai_test_status_var.set("OpenAI: Schlüssel OK"))
                    self.after(0, lambda: openai_balance_var.set(balance_text))
                except OpenAIError as exc:
                    self.after(0, lambda: openai_test_status_var.set(f"OpenAI: {exc.user_message()}"))
                    self.after(0, lambda: openai_balance_var.set("Guthaben: k.A."))
                except Exception:
                    self.after(0, lambda: openai_test_status_var.set("OpenAI-Prüfung fehlgeschlagen"))
                    self.after(0, lambda: openai_balance_var.set("Guthaben: k.A."))
            threading.Thread(target=run_check, daemon=True).start()

        openai_actions = ttk.Frame(api_tab)
        openai_actions.grid(row=11, column=0, columnspan=4, sticky="ew", pady=4)
        ttk.Button(openai_actions, text="OpenAI-Schlüssel prüfen", command=check_openai_key).pack(side="left")
        ttk.Label(openai_actions, textvariable=openai_test_status_var, wraplength=520, foreground="#555555").pack(side="left", padx=(12, 0))
        ttk.Label(api_tab, textvariable=openai_balance_var, wraplength=520, foreground="#555555").grid(row=12, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 4))

        ttk.Label(ftp_tab, text="FTP-Deployment", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(ftp_tab, text="FTP-Server:").grid(row=1, column=0, sticky="w", pady=4)
        ftp_host_var = tk.StringVar(value=self.config_data.get("ftp_host", "w0210fa6.kasserver.com"))
        ttk.Entry(ftp_tab, textvariable=ftp_host_var).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="Port:").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        ftp_port_var = tk.StringVar(value=self.config_data.get("ftp_port", "21"))
        ttk.Entry(ftp_tab, textvariable=ftp_port_var, width=8).grid(row=1, column=3, sticky="w", padx=6, pady=4)
        ttk.Label(ftp_tab, text="FTP-Benutzer:").grid(row=2, column=0, sticky="w", pady=4)
        ftp_user_var = tk.StringVar(value=self.config_data.get("ftp_user", "f0185adc"))
        ttk.Entry(ftp_tab, textvariable=ftp_user_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="FTP-Passwort:").grid(row=3, column=0, sticky="w", pady=4)
        ftp_password_var = tk.StringVar(value="")
        ttk.Entry(ftp_tab, textvariable=ftp_password_var, show="*").grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ftp_saved = bool(str(self.config_data.get("ftp_password_dpapi", "") or "").strip())
        ftp_status_var = tk.StringVar(value="FTP-Passwort ist verschlüsselt gespeichert." if ftp_saved else "FTP-Passwort noch nicht gespeichert.")
        ttk.Label(ftp_tab, text="Leer lassen, um ein bereits gespeichertes Passwort zu behalten.", wraplength=720).grid(row=4, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        ttk.Label(ftp_tab, text="Lokale routes.php:").grid(row=5, column=0, sticky="w", pady=4)
        ftp_local_routes_path_var = tk.StringVar(value=self.config_data.get("ftp_local_routes_path", "server/routes.php"))
        ttk.Entry(ftp_tab, textvariable=ftp_local_routes_path_var).grid(row=5, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="Zielpfad routes.php:").grid(row=6, column=0, sticky="w", pady=4)
        ftp_routes_path_var = tk.StringVar(value=self.config_data.get("ftp_remote_routes_path", "/ortschronik.info/ortschronik-api/routes.php"))
        ttk.Entry(ftp_tab, textvariable=ftp_routes_path_var).grid(row=6, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        def current_ftp_password() -> str:
            password = ftp_password_var.get()
            if password:
                return password
            encrypted = str(self.config_data.get("ftp_password_dpapi", "") or "")
            if not encrypted:
                return ""
            return unprotect_text(encrypted)

        def check_ftp_connection() -> None:
            ftp_status_var.set("FTP prüft ...")

            def run_check() -> None:
                try:
                    host = ftp_host_var.get().strip()
                    user = ftp_user_var.get().strip()
                    port = int(ftp_port_var.get().strip() or "21")
                    password = current_ftp_password()
                    if not host or not user or not password:
                        raise SecureStoreError("Bitte FTP-Server, Benutzer und Passwort erfassen.")
                    target_dir = posixpath.dirname(ftp_routes_path_var.get().strip())
                    with ftplib.FTP() as ftp:
                        ftp.connect(host, port, timeout=20)
                        ftp.login(user, password)
                        if target_dir and target_dir != ".":
                            ftp.cwd(target_dir)
                    self.after(0, lambda: ftp_status_var.set("FTP: Verbindung OK"))
                except Exception as exc:
                    self.after(0, lambda: ftp_status_var.set(f"FTP: {exc}"))

            threading.Thread(target=run_check, daemon=True).start()

        ftp_buttons = ttk.Frame(ftp_tab)
        ftp_buttons.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(8, 8))
        ttk.Button(ftp_buttons, text="FTP-Verbindung prüfen", command=check_ftp_connection).pack(side="left")
        ttk.Label(ftp_buttons, textvariable=ftp_status_var, foreground="#555555", wraplength=620).pack(side="left", padx=(12, 0))

        ttk.Label(links_tab, text="Nextcloud und Hinweise", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(links_tab, text="Nextcloud Web-Dateiansicht:").grid(row=1, column=0, sticky="w", pady=4)
        nc_web_var = tk.StringVar(value=self.config_data.get("nextcloud_web_files_url", "https://nx94165.your-storageshare.de/apps/files/files"))
        ttk.Entry(links_tab, textvariable=nc_web_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(links_tab, text="Beispiel: https://nx94165.your-storageshare.de/apps/files/files  ·  Links zeigen auf den betreffenden Nextcloud-Ordner.", wraplength=760).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 10))
        ttk.Label(links_tab, text="Das Datenbankpasswort und SMTP-Passwort liegen nur auf dem Server/API. Das FTP-Passwort wird lokal per Windows-DPAPI verschlüsselt. Die OpenAI-Punkte je Metadatenfeld ändern Sie unter Admin > Punkteregeln verwalten.", wraplength=760).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 10))

        tracked_vars = [
            folder_name_var, api_url_var, openai_key_var, openai_model_var,
            openai_pdf_pages_var, openai_text_chars_var, openai_points_var,
            mysql_host_var, mysql_port_var, mysql_database_var, mysql_user_var,
            ftp_host_var, ftp_port_var, ftp_user_var, ftp_password_var,
            ftp_local_routes_path_var, ftp_routes_path_var, nc_web_var,
        ]
        for var in tracked_vars:
            var.trace_add("write", mark_dirty)

        def update_preview(*_):
            old = self.config_data.get("metadata_folder_name", ".ortschronik_metadaten")
            self.config_data["metadata_folder_name"] = folder_name_var.get().strip() or ".ortschronik_metadaten"
            self.ensure_standard_metadata_folder()
            meta_preview_var.set(self.metadata_folder_var.get())
            self.config_data["metadata_folder_name"] = old
            self.ensure_standard_metadata_folder()
        folder_name_var.trace_add("write", update_preview)

        def save_settings(close_after: bool = True) -> bool:
            saving_var.set(True)
            name = folder_name_var.get().strip() or ".ortschronik_metadaten"
            if not name.startswith("."):
                name = "." + name
            folders = [line.strip() for line in work_text.get("1.0", "end").splitlines() if line.strip()]
            if not folders:
                messagebox.showwarning("Admin-Ordner", "Bitte mindestens einen Admin-Bearbeitungsordner erfassen.", parent=dialog)
                saving_var.set(False)
                return False
            try:
                openai_pdf_pages = max(1, min(100, int(openai_pdf_pages_var.get())))
                openai_text_chars = max(500, min(100000, int(openai_text_chars_var.get())))
                openai_points = max(0, min(50, int(openai_points_var.get())))
            except ValueError:
                messagebox.showwarning("OpenAI-Auszug", "Bitte gültige Zahlen für Seiten, Zeichen und OpenAI-Punkte erfassen.", parent=dialog)
                saving_var.set(False)
                return False
            self.config_data["metadata_folder_name"] = name
            self.admin_work_folder_names = set(folders)
            self.config_data["admin_work_folder_names"] = sorted(self.admin_work_folder_names)
            self.config_data["api_url"] = api_url_var.get().strip()
            self.config_data["openai_api_key"] = openai_key_var.get().strip()
            self.config_data["openai_model"] = openai_model_var.get().strip() or "gpt-3.5-turbo"
            self.config_data["openai_pdf_sample_pages"] = openai_pdf_pages
            self.config_data["openai_text_sample_chars"] = openai_text_chars
            self.config_data["openai_metadata_points"] = openai_points
            self.config_data["mysql_host"] = mysql_host_var.get().strip()
            self.config_data["mysql_port"] = mysql_port_var.get().strip() or "3306"
            self.config_data["mysql_database"] = mysql_database_var.get().strip()
            self.config_data["mysql_user"] = mysql_user_var.get().strip()
            self.config_data["ftp_host"] = ftp_host_var.get().strip()
            self.config_data["ftp_port"] = ftp_port_var.get().strip() or "21"
            self.config_data["ftp_user"] = ftp_user_var.get().strip()
            self.config_data["ftp_local_routes_path"] = ftp_local_routes_path_var.get().strip() or "server/routes.php"
            self.config_data["ftp_remote_routes_path"] = ftp_routes_path_var.get().strip()
            if ftp_password_var.get():
                try:
                    self.config_data["ftp_password_dpapi"] = protect_text(ftp_password_var.get())
                except SecureStoreError as exc:
                    messagebox.showwarning("FTP-Passwort", str(exc), parent=dialog)
                    saving_var.set(False)
                    return False
            self.config_data["nextcloud_web_files_url"] = nc_web_var.get().strip()
            self.ensure_standard_metadata_folder()
            save_config(self.config_data)
            # OpenAI-Punkte werden feldbezogen in der Punkteverwaltung gepflegt.
            add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Admin-Einstellungen geändert", f"Metadatenordner={name}; Admin-Ordner={', '.join(folders)}"))
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            dirty_var.set(False)
            saving_var.set(False)
            messagebox.showinfo("Admin-Einstellungen", "Einstellungen wurden gespeichert.", parent=dialog)
            if close_after:
                dialog.destroy()
            return True

        def close_dialog() -> None:
            if not dirty_var.get():
                dialog.destroy()
                return
            answer = messagebox.askyesnocancel(
                "Änderungen speichern?",
                "Es gibt ungespeicherte Änderungen in den Admin-Einstellungen.\n\nSollen sie vor dem Schließen gespeichert werden?",
                parent=dialog,
            )
            if answer is None:
                return
            if answer:
                save_settings(close_after=True)
                return
            dialog.destroy()

        buttons = ttk.Frame(header)
        buttons.grid(row=0, column=1, sticky="e")
        ttk.Button(buttons, text="Speichern", command=lambda: save_settings(close_after=False)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=close_dialog).pack(side="left", padx=6)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dirty_var.set(False)

    # Upload
    def api_document_to_item(self, document: dict, persons: list | None = None, history: list | None = None) -> dict:
        """Wandelt einen API-Dokumentdatensatz in die lokale Metadatenstruktur der Oberfläche um."""
        item = dict(document or {})
        item["uploaded_by"] = item.get("uploaded_by_name") or item.get("uploaded_by") or ""
        item.setdefault("uploaded_by_user_id", item.get("user_id", ""))
        item["persons"] = persons if persons is not None else item.get("persons", []) or []
        item["history"] = history if history is not None else item.get("history", []) or []
        # Zusatzinformationen aus json_metadata übernehmen, sofern vorhanden.
        raw_json_metadata = item.get("json_metadata")
        if isinstance(raw_json_metadata, str) and raw_json_metadata.strip():
            try:
                parsed_json_metadata = json.loads(raw_json_metadata)
                if isinstance(parsed_json_metadata, dict):
                    for extra_key in (
                        "odv_capture_mode",
                        "odv_captured_by_admin",
                        "archived_from_path",
                        "ocr_pdf_path",
                        "ocr_pdf_filename",
                        "ocr_source_filename",
                        "ocr_created_at",
                        "openai_metadata_fields",
                        "openai_metadata_model",
                        "openai_metadata_applied_at",
                        "gps_coordinates",
                        "gps_place",
                    ):
                        if extra_key in parsed_json_metadata and extra_key not in item:
                            item[extra_key] = parsed_json_metadata.get(extra_key)
                    metadata = parsed_json_metadata.get("metadata") if isinstance(parsed_json_metadata.get("metadata"), dict) else {}
                    if "gps_coordinates" in metadata and "gps_coordinates" not in item:
                        item["gps_coordinates"] = metadata.get("gps_coordinates")
                    if "gps_place" in metadata and "gps_place" not in item:
                        item["gps_place"] = metadata.get("gps_place")
            except Exception:
                pass
        # Kompatibilitätsfelder für ältere JSON-Ansichten
        item.setdefault("primary_source", item.get("primaerquelle", ""))
        item.setdefault("secondary_source", item.get("sekundaerquelle", item.get("source", item.get("quelle", ""))))
        item.setdefault("source", item.get("secondary_source", item.get("quelle", "")))
        item.setdefault("original_location", item.get("standort_original", ""))
        item.setdefault("document_date", item.get("datum", ""))
        item.setdefault("event", item.get("ereignis", ""))
        item.setdefault("place", item.get("ort", ""))
        item.setdefault("gps_coordinates", item.get("gps", item.get("gps_koordinaten", "")))
        item.setdefault("gps_place", item.get("gps_ort", item.get("gps_location", "")))
        item.setdefault("description", item.get("beschreibung", ""))
        item.setdefault("note", item.get("bemerkung", ""))
        item.setdefault("keywords", item.get("stichwoerter", ""))
        item.setdefault("transcription_done", item.get("transcription_done", ""))
        item.setdefault("transcription_type", item.get("transcription_type", ""))
        item.setdefault("transcription_note", item.get("transcription_note", ""))
        return item

    def api_get_document_item(self, upload_id: str) -> dict | None:
        if not self.api_token or not upload_id:
            return None
        try:
            response = self.api.get_document(self.api_token, upload_id)
            return self.api_document_to_item(
                response.get("document", {}) or {},
                response.get("persons", []) or [],
                response.get("history", []) or [],
            )
        except ApiError as exc:
            messagebox.showwarning("API", f"Dokument konnte nicht aus MySQL geladen werden:\n{exc}")
            return None

    def item_payload_for_api(self, item: dict) -> dict:
        """Erzeugt aus einem lokalen/API-Item den Payload für PUT /api/documents/{upload_id}."""
        return {
            "current_filename": item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "",
            "target_folder": item.get("target_folder") or "",
            "current_path": item.get("current_path") or "",
            "status": item.get("status") or "hochgeladen",
            "person_status": item.get("person_status") or ("identified" if item.get("persons") else "none"),
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "archived_from_path": item.get("archived_from_path", ""),
            "ocr_pdf_path": item.get("ocr_pdf_path", ""),
            "ocr_pdf_filename": item.get("ocr_pdf_filename", ""),
            "ocr_source_filename": item.get("ocr_source_filename", ""),
            "ocr_created_at": item.get("ocr_created_at", ""),
            "openai_metadata_fields": item.get("openai_metadata_fields", []) or [],
            "openai_metadata_model": item.get("openai_metadata_model", ""),
            "openai_metadata_applied_at": item.get("openai_metadata_applied_at", ""),
            "metadata": {
                "document_type": item.get("document_type", ""),
                "primary_source": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "primaerquelle": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "secondary_source": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "sekundaerquelle": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "source": item.get("secondary_source", item.get("source", "")),
                "quelle": item.get("secondary_source", item.get("source", "")),
                "original_location": item.get("original_location", ""),
                "standort_original": item.get("original_location", ""),
                "document_date": item.get("document_date", ""),
                "datum": item.get("document_date", ""),
                "event": item.get("event", ""),
                "ereignis": item.get("event", ""),
                "place": item.get("place", ""),
                "ort": item.get("place", ""),
                "gps_coordinates": item.get("gps_coordinates", ""),
                "gps_koordinaten": item.get("gps_coordinates", ""),
                "gps_place": item.get("gps_place", ""),
                "gps_ort": item.get("gps_place", ""),
                "description": item.get("description", ""),
                "beschreibung": item.get("description", ""),
                "note": item.get("note", ""),
                "bemerkung": item.get("note", ""),
                "copyright_author": item.get("copyright_author", ""),
                "urheber": item.get("copyright_author", ""),
                "rights_holder": item.get("rights_holder", ""),
                "rechteinhaber": item.get("rights_holder", ""),
                "usage_permission": item.get("usage_permission", ""),
                "nutzungsfreigabe": item.get("usage_permission", ""),
                "license_note": item.get("license_note", ""),
                "lizenz": item.get("license_note", ""),
                "rights_note": item.get("rights_note", ""),
                "rechte": item.get("rights_note", ""),
                "archive_name": item.get("archive_name", ""),
                "archiv": item.get("archive_name", ""),
                "archive_signature": item.get("archive_signature", ""),
                "signatur": item.get("archive_signature", ""),
                "archive_accessed_at": item.get("archive_accessed_at", ""),
                "abruf_am": item.get("archive_accessed_at", ""),
                "keywords": item.get("keywords", ""),
                "stichwoerter": item.get("keywords", ""),
                "transcription_done": item.get("transcription_done", ""),
                "transcription_type": item.get("transcription_type", ""),
                "transcription_note": item.get("transcription_note", ""),
                "ocr_pdf_path": item.get("ocr_pdf_path", ""),
                "ocr_pdf_filename": item.get("ocr_pdf_filename", ""),
                "ocr_source_filename": item.get("ocr_source_filename", ""),
                "ocr_created_at": item.get("ocr_created_at", ""),
                "openai_metadata_fields": item.get("openai_metadata_fields", []) or [],
                "openai_metadata_model": item.get("openai_metadata_model", ""),
                "openai_metadata_applied_at": item.get("openai_metadata_applied_at", ""),
            },
        }


    def item_create_payload_for_api(self, item: dict) -> dict:
        """Erzeugt aus einem lokalen Item den Payload für POST /api/documents.

        Wird auch für Dateien verwendet, die physisch bereits im Nextcloud-Ordner liegen
        und erst durch die Metadatenerfassung in ODV/MySQL übernommen werden.
        """
        payload = self.item_payload_for_api(item)
        payload.update({
            "upload_id": item.get("upload_id") or "",
            "original_filename": item.get("original_filename") or item.get("current_filename") or Path(str(item.get("current_path", ""))).name,
            "stored_filename": item.get("stored_filename") or item.get("current_filename") or Path(str(item.get("current_path", ""))).name,
            "current_filename": item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or Path(str(item.get("current_path", ""))).name,
            "target_folder": (item.get("target_folder") or (str(Path(str(item.get("current_path", ""))).parent) if item.get("current_path") else "")),
            "current_path": item.get("current_path") or "",
            "uploaded_at": str(item.get("uploaded_at", "")).replace("T", " ") or datetime.now().isoformat(timespec="seconds").replace("T", " "),
            "uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "uploaded_by_name": item.get("uploaded_by_name") or item.get("uploaded_by") or "",
            "import_uploaded_by_user_id": item.get("uploaded_by_user_id") or item.get("user_id") or "",
            "status": item.get("status") or ("erfasst" if item.get("odv_capture_mode") == "existing_file_metadata" else "hochgeladen"),
            "person_status": item.get("person_status") or ("identified" if item.get("persons") else "none"),
            "odv_capture_mode": item.get("odv_capture_mode") or "odv_upload",
            "odv_captured_by_admin": bool(item.get("odv_captured_by_admin", False)),
            "persons": item.get("persons", []) or [],
        })
        return payload

    def save_item_to_api(self, item: dict) -> tuple[bool, str]:
        upload_id = str(item.get("upload_id", "") or "")
        if not self.api_token or not upload_id:
            return False, "Kein API-Token oder keine Upload-ID vorhanden"
        try:
            try:
                self.api.lock_document(self.api_token, upload_id)
            except ApiError as lock_exc:
                return False, str(lock_exc)
            self.api.update_document(self.api_token, upload_id, self.item_payload_for_api(item))
            return True, "MySQL aktualisiert"
        except ApiError as exc:
            app_log_exception("Upload-Metadaten konnten nicht in MySQL gespeichert werden", exc, upload_id=upload_id)
            return False, str(exc)

    def save_item_json_if_present(self, item: dict) -> None:
        metadata_file = item.get("_metadata_file")
        if metadata_file:
            try:
                save_metadata_file(Path(str(metadata_file)), item)
            except Exception:
                pass

    def metadata_payload_for_api(self, metadata: UploadMetadata) -> dict:
        data = metadata.to_dict()
        return {
            "upload_id": data.get("upload_id"),
            "original_filename": data.get("original_filename"),
            "stored_filename": data.get("stored_filename"),
            "current_filename": data.get("current_filename"),
            "target_folder": data.get("target_folder"),
            "current_path": data.get("current_path"),
            "uploaded_at": str(data.get("uploaded_at", "")).replace("T", " "),
            "status": data.get("status", "hochgeladen"),
            "person_status": data.get("person_status", "none"),
            "metadata": {
                "document_type": data.get("document_type", ""),
                "primary_source": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "primaerquelle": item.get("primary_source", "") if "item" in locals() else data.get("primary_source", ""),
                "secondary_source": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "sekundaerquelle": item.get("secondary_source", "") if "item" in locals() else data.get("secondary_source", ""),
                "source": data.get("secondary_source", data.get("source", "")),
                "quelle": data.get("secondary_source", data.get("source", "")),
                "original_location": data.get("original_location", ""),
                "standort_original": data.get("original_location", ""),
                "document_date": data.get("document_date", ""),
                "datum": data.get("document_date", ""),
                "event": data.get("event", ""),
                "ereignis": data.get("event", ""),
                "place": data.get("place", ""),
                "ort": data.get("place", ""),
                "gps_coordinates": data.get("gps_coordinates", ""),
                "gps_koordinaten": data.get("gps_coordinates", ""),
                "gps_place": data.get("gps_place", ""),
                "gps_ort": data.get("gps_place", ""),
                "description": data.get("description", ""),
                "beschreibung": data.get("description", ""),
                "note": data.get("note", ""),
                "bemerkung": data.get("note", ""),
                "copyright_author": data.get("copyright_author", ""),
                "urheber": data.get("copyright_author", ""),
                "rights_holder": data.get("rights_holder", ""),
                "rechteinhaber": data.get("rights_holder", ""),
                "usage_permission": data.get("usage_permission", ""),
                "nutzungsfreigabe": data.get("usage_permission", ""),
                "license_note": data.get("license_note", ""),
                "lizenz": data.get("license_note", ""),
                "rights_note": data.get("rights_note", ""),
                "rechte": data.get("rights_note", ""),
                "archive_name": data.get("archive_name", ""),
                "archiv": data.get("archive_name", ""),
                "archive_signature": data.get("archive_signature", ""),
                "signatur": data.get("archive_signature", ""),
                "archive_accessed_at": data.get("archive_accessed_at", ""),
                "abruf_am": data.get("archive_accessed_at", ""),
                "keywords": data.get("keywords", ""),
                "stichwoerter": data.get("keywords", ""),
                "transcription_done": data.get("transcription_done", False),
                "transcription_type": data.get("transcription_type", ""),
                "transcription_note": data.get("transcription_note", ""),
                "ocr_pdf_path": data.get("ocr_pdf_path", ""),
                "ocr_pdf_filename": data.get("ocr_pdf_filename", ""),
                "ocr_source_filename": data.get("ocr_source_filename", ""),
                "ocr_created_at": data.get("ocr_created_at", ""),
                "openai_metadata_fields": data.get("openai_metadata_fields", []) or [],
                "openai_metadata_model": data.get("openai_metadata_model", ""),
                "openai_metadata_applied_at": data.get("openai_metadata_applied_at", ""),
            },
            "persons": data.get("persons", []),
        }

    def save_upload_to_api(self, metadata: UploadMetadata) -> tuple[bool, str]:
        if not self.api_token:
            return False, "Kein API-Token vorhanden"
        try:
            payload = self.metadata_payload_for_api(metadata)
            self.api.create_document(self.api_token, payload)
            persons = payload.get("persons") or []
            if persons:
                self.api.update_persons(self.api_token, metadata.upload_id, persons)
            return True, "Metadaten wurden in MySQL gespeichert"
        except ApiError as exc:
            app_log_exception("Upload-Metadaten konnten nicht in MySQL gespeichert werden", exc, upload_id=upload_id)
            return False, str(exc)

    def build_upload_metadata_for_source(self, source: Path, target_folder: Path, display_name: str) -> UploadMetadata:
        upload_id = make_upload_id()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_{safe_filename(source.name)}"
        current_path = str(target_folder / stored_filename)
        document_type = self.meta_vars["document_type"].get().strip()
        if document_type in {"", "Mehrere Dateien"}:
            document_type = detect_document_type(source)
        self.remember_document_type(document_type)
        self.remember_archive_collection(self.meta_vars["archive_name"].get().strip())
        ocr_source = self.current_upload_ocr_pdf_path() if getattr(self, "selected_file", None) == source else None
        ocr_planned_path = self.planned_upload_ocr_pdf_path(source, target_folder, stored_filename) if ocr_source else ""
        openai_fields = list(dict.fromkeys(str(field) for field in (getattr(self, "openai_metadata_applied_fields", []) or []) if str(field).strip()))
        return UploadMetadata(
            upload_id=upload_id,
            original_filename=source.name,
            stored_filename=stored_filename,
            current_filename=stored_filename,
            current_path=current_path,
            status="hochgeladen",
            uploaded_by=display_name,
            uploaded_at=datetime.now().isoformat(timespec="seconds"),
            target_folder=str(target_folder),
            primary_source=self.meta_vars.get("primary_source", tk.StringVar()).get().strip(),
            secondary_source=self.meta_vars.get("secondary_source", tk.StringVar()).get().strip(),
            source=self.meta_vars.get("secondary_source", tk.StringVar()).get().strip(),
            original_location=self.meta_vars["original_location"].get().strip(),
            document_date=self.meta_vars["document_date"].get().strip(),
            event=self.meta_vars["event"].get().strip(),
            place=self.meta_vars["place"].get().strip(),
            gps_coordinates=self.meta_vars.get("gps_coordinates", tk.StringVar()).get().strip(),
            gps_place=self.meta_vars.get("gps_place", tk.StringVar()).get().strip(),
            document_type=document_type,
            rights_note=self.meta_vars["rights_note"].get().strip(),
            copyright_author=self.meta_vars["copyright_author"].get().strip(),
            rights_holder=self.meta_vars["rights_holder"].get().strip(),
            usage_permission=self.meta_vars["usage_permission"].get().strip(),
            license_note=self.meta_vars["license_note"].get().strip(),
            archive_name=self.meta_vars["archive_name"].get().strip(),
            archive_signature=self.meta_vars["archive_signature"].get().strip(),
            archive_accessed_at=self.meta_vars["archive_accessed_at"].get().strip(),
            keywords=str(self.meta_vars.get("keywords", tk.StringVar()).get()).strip(),
            transcription_done=bool(self.meta_vars.get("transcription_done", tk.BooleanVar(value=False)).get()),
            transcription_type=str(self.meta_vars.get("transcription_type", tk.StringVar()).get()).strip(),
            transcription_note=self.meta_vars.get("transcription_note", tk.StringVar()).get().strip(),
            ocr_pdf_path=ocr_planned_path,
            ocr_pdf_filename=Path(ocr_planned_path).name if ocr_planned_path else "",
            ocr_source_filename=ocr_source.name if ocr_source else "",
            ocr_created_at=datetime.now().isoformat(timespec="seconds") if ocr_source else "",
            openai_metadata_fields=openai_fields,
            openai_metadata_model=str(self.config_data.get("openai_model", "") or "") if openai_fields else "",
            openai_metadata_applied_at=datetime.now().isoformat(timespec="seconds") if openai_fields else "",
            description=self.description_text.get("1.0", "end").strip(),
            note=self.note_text.get("1.0", "end").strip(),
            person_status=self.person_status_var.get() if self.selected_file else "none",
            persons=self.persons if self.selected_file else [],
        )

    def planned_upload_ocr_pdf_path(self, source: Path, target_folder: Path, stored_filename: str) -> str:
        if getattr(self, "selected_file", None) != source:
            return ""
        ocr_source = self.current_upload_ocr_pdf_path()
        if not ocr_source:
            return ""
        target = target_folder / f"{Path(stored_filename).stem}_ocr.pdf"
        return str(unique_path_with_counter(target))

    def upload_single_source_file(self, source: Path, target_folder: Path, display_name: str) -> tuple[bool, str]:
        metadata = self.build_upload_metadata_for_source(source, target_folder, display_name)
        metadata_folder = self.metadata_folder_path()
        target_file, json_file = copy_with_metadata(source, target_folder, metadata, metadata_folder)
        with json_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        append_metadata_history(data, display_name, "Datei hochgeladen", f"{source.name} → {target_file}")
        ocr_source = self.current_upload_ocr_pdf_path() if getattr(self, "selected_file", None) == source else None
        ocr_target_text = str(data.get("ocr_pdf_path") or "")
        if ocr_source and ocr_target_text:
            ocr_target = Path(ocr_target_text)
            try:
                ocr_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ocr_source, ocr_target)
                data["ocr_pdf_path"] = str(ocr_target)
                data["ocr_pdf_filename"] = ocr_target.name
                data["ocr_source_filename"] = ocr_source.name
                append_metadata_history(data, display_name, "OCR-PDF verknüpft", f"{ocr_source.name} → {ocr_target}")
            except Exception as exc:
                app_log_exception("OCR-PDF konnte nicht zum Upload kopiert werden", exc, source=str(ocr_source), target=ocr_target_text)
                raise RuntimeError(f"Original wurde kopiert, aber OCR-PDF konnte nicht verknüpft werden:\n{exc}") from exc
        save_metadata_file(json_file, data)
        api_ok, api_message = self.save_upload_to_api(metadata)
        if api_ok:
            append_metadata_history(data, display_name, "MySQL gespeichert", "Metadaten wurden über die API in MySQL gespeichert")
        else:
            append_metadata_history(data, display_name, "MySQL nicht gespeichert", api_message)
        save_metadata_file(json_file, data)
        add_history(HistoryEntry.now(display_name, "Datei hochgeladen", f"{source.name} → {target_file} | Metadaten: {json_file}", metadata.upload_id))
        if api_ok:
            add_history(HistoryEntry.now(display_name, "MySQL gespeichert", api_message, metadata.upload_id))
        else:
            add_history(HistoryEntry.now(display_name, "MySQL nicht gespeichert", api_message, metadata.upload_id))
        if metadata.persons:
            add_history(HistoryEntry.now(display_name, "Personen markiert", f"{len(metadata.persons)} Personen in {metadata.stored_filename}", metadata.upload_id))
        if not api_ok:
            raise RuntimeError(api_message or "Die Datei wurde lokal kopiert, konnte aber nicht in MySQL/API gespeichert werden.")
        return api_ok, str(target_file)

    def submit_upload(self) -> None:
        base = self.nextcloud_base_path(show_message=True)
        if base is None:
            return
        selected_target = self.target_folder_var.get().strip()
        target_folder = self.target_folder_map.get(selected_target)
        if target_folder is None and selected_target:
            candidate = Path(selected_target).expanduser()
            if not candidate.is_absolute():
                candidate = base / selected_target
            target_folder = candidate
        if target_folder is None or not target_folder.exists() or not target_folder.is_dir() or not self.is_path_under_base(target_folder, base):
            messagebox.showerror("Fehler", "Bitte einen gültigen Zielordner innerhalb des Nextcloud-Stammverzeichnisses auswählen.")
            return

        display_name = self.display_name_var.get().strip() or "Ortschronist/in"
        self.ensure_standard_metadata_folder()
        save_config(self.config_data)

        if self.selected_folder:
            source_folder = self.selected_folder
            if not source_folder.exists() or not source_folder.is_dir():
                messagebox.showerror("Fehler", "Bitte einen gültigen Ordner auswählen.")
                return
            files = [p for p in sorted(source_folder.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and not p.name.startswith(".")]
            if not files:
                messagebox.showinfo("Ordnerupload", "Im ausgewählten Ordner wurden keine Dateien gefunden.")
                return
            if not messagebox.askyesno("Ordner hochladen", f"{len(files)} Datei(en) mit den aktuell erfassten Metadaten hochladen?\n\nOrdner:\n{source_folder}"):
                return
            ok_count = 0
            fail_count = 0
            for source in files:
                try:
                    rel_parent = source.relative_to(source_folder).parent
                    file_target_folder = target_folder / rel_parent if str(rel_parent) != "." else target_folder
                    file_target_folder.mkdir(parents=True, exist_ok=True)
                    self.upload_single_source_file(source, file_target_folder, display_name)
                    ok_count += 1
                except Exception as exc:
                    fail_count += 1
                    app_log_exception("Datei im Ordnerupload konnte nicht hochgeladen werden", exc, path=str(source))
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            messagebox.showinfo("Ordnerupload", f"Hochgeladen: {ok_count}\nFehler: {fail_count}")
            self.clear_upload_form(keep_target_folder=True)
            return

        source = self.selected_file or Path(self.file_var.get().strip())
        if not source.exists() or not source.is_file():
            messagebox.showerror("Fehler", "Bitte eine gültige Datei oder einen Ordner auswählen.")
            return
        try:
            api_ok, target_file = self.upload_single_source_file(source, target_folder, display_name)
        except Exception as exc:
            messagebox.showerror("Fehler beim Kopieren", str(exc))
            return
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Erfolg", f"Datei wurde hochgeladen:\n{target_file}")
        self.clear_upload_form(keep_target_folder=True)

    def clear_upload_form(self, keep_target_folder: bool = True) -> None:
        selected_target = self.target_folder_var.get()
        self.selected_file = None
        self.selected_folder = None
        if hasattr(self, "upload_ocr_pdf_path"):
            self.upload_ocr_pdf_path = None
        self.file_var.set("")
        for key, var in self.meta_vars.items():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set(self.place_var.get().strip() if key == "place" else "")
        self.description_text.delete("1.0", "end")
        if getattr(self, "upload_description_counter_var", None):
            self.update_description_counter(self.description_text, self.upload_description_counter_var)
        self.note_text.delete("1.0", "end")
        self.person_status_var.set("none")
        self.persons = []
        self.person_summary_var.set("Keine Personen markiert.")
        if getattr(self, "upload_wizard", None):
            try:
                self.upload_wizard.show_step(0)
            except Exception:
                pass
        if getattr(self, "update_upload_status_indicator", None):
            try:
                self.update_upload_status_indicator()
            except Exception:
                pass
        if getattr(self, "upload_openai_text_var", None):
            try:
                self.upload_openai_text_var.set("OpenAI: nicht geprüft")
            except Exception:
                pass
        if getattr(self, "upload_openai_usage_var", None):
            try:
                self.upload_openai_usage_var.set("Verbrauch: k.A.")
            except Exception:
                pass
        if getattr(self, "update_openai_precheck_indicator", None):
            try:
                self.update_openai_precheck_indicator()
            except Exception:
                pass
        if keep_target_folder:
            self.target_folder_var.set(selected_target)

    # Admin
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
        # Punkte-Buttons bleiben im eigenen Punkteblock sichtbar; fachliche Berechtigung
        # wird beim Öffnen der Dialoge geprüft.
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
        """Filtert nachträglich erfasste vorhandene Dateien für die Admin-Bearbeitungsliste."""
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

    def clear_admin_selection(self) -> None:
        """Leert Admin-Detailbereich, bis ein Upload aktiv ausgewählt wird."""
        try:
            self.admin_tree.selection_remove(self.admin_tree.selection())
        except Exception:
            pass
        if hasattr(self, "admin_preview_label"):
            self.admin_preview_image = None
            self.admin_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        if hasattr(self, "admin_show_persons_check"):
            self.admin_show_persons_check.grid_remove()
        if hasattr(self, "admin_person_legend_frame"):
            self.admin_person_legend_frame.grid_remove()
        if hasattr(self, "admin_person_legend_text"):
            self.admin_person_legend_text.configure(state="normal")
            self.admin_person_legend_text.delete("1.0", "end")
            self.admin_person_legend_text.configure(state="disabled")
        if hasattr(self, "admin_meta_vars"):
            for var in self.admin_meta_vars.values():
                var.set("")
        for attr in ("admin_description_text", "admin_note_text", "admin_json_text"):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.configure(state="normal")
                    widget.delete("1.0", "end")
                    if attr == "admin_json_text":
                        widget.insert("1.0", "Keine Datei ausgewählt.")
                        widget.configure(state="disabled")
                except Exception:
                    pass
        if hasattr(self, "admin_new_filename_var"):
            self.admin_new_filename_var.set("")
        if hasattr(self, "admin_document_points_var"):
            self.admin_document_points_var.set("keine Datei ausgewählt")

    def selected_admin_upload(self) -> dict | None:
        selection = self.admin_tree.selection()
        if not selection:
            return None
        upload_id = selection[0]
        for item in self.admin_uploads:
            if item.get("upload_id") == upload_id:
                return item
        return None

    def set_admin_legend(self, lines: list[str]) -> None:
        if hasattr(self, "admin_person_legend_text"):
            self.admin_person_legend_text.configure(state="normal")
            self.admin_person_legend_text.delete("1.0", "end")
            self.admin_person_legend_text.insert("1.0", "\n".join(lines) if lines else "Keine Personenangaben.")
            self.admin_person_legend_text.configure(state="disabled")

    def show_admin_preview(self, item: dict) -> None:
        self.normalize_admin_item_path_for_current_pc(item)
        path = self.resolve_document_local_path(item)
        def hide_person_ui():
            if hasattr(self, "admin_person_legend_frame"):
                self.admin_person_legend_frame.grid_remove()
            if hasattr(self, "admin_show_persons_check"):
                self.admin_show_persons_check.grid_remove()
            self.set_admin_legend([])
        if not path or not path.exists() or path.is_dir():
            if hasattr(self, "admin_preview_label"):
                message = "Keine Datei ausgewählt." if not item else "Datei nicht gefunden."
                self.admin_preview_label.configure(image="", text=message)
            hide_person_ui()
            return
        if not is_image_file(path):
            if hasattr(self, "admin_preview_label"):
                self.admin_preview_label.configure(image="", text=f"Keine Bildvorschau für:\n{path.name}")
            hide_person_ui()
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
            hide_person_ui()


    def update_admin_document_points_display(self, upload_id: str) -> None:
        if not hasattr(self, "admin_document_points_var"):
            return
        if not upload_id or not self.api_token:
            self.admin_document_points_var.set("keine Punkte geladen")
            return
        try:
            resp = self.api.document_points(self.api_token, upload_id)
            rows = resp.get("points", []) or []
            total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1)
            auto_total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1 and int(r.get("is_manual", 0) or 0) == 0)
            manual_total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1 and int(r.get("is_manual", 0) or 0) == 1)
            if not rows:
                self.admin_document_points_var.set("0")
            else:
                self.admin_document_points_var.set(f"{total} gesamt · automatisch {auto_total} · Sonder {manual_total}")
        except Exception as exc:
            self.admin_document_points_var.set("nicht geladen")
            app_log_exception("Dokumentpunkte konnten nicht geladen werden", exc, upload_id=upload_id)

    def recalculate_points_for_visible_admin_uploads(self) -> None:
        """Berechnet fehlende automatische Punkte für alle aktuell angezeigten Admin-Datensätze nach.

        Die API legt wegen Unique-Keys keine Dubletten für dieselbe Datei/Feld/Regel/Begünstigten an.
        """
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Nachberechnung ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für die Punkteberechnung ist eine API-Anmeldung erforderlich.")
            return
        if not hasattr(self, "admin_tree"):
            return
        upload_ids = list(self.admin_tree.get_children(""))
        if not upload_ids:
            messagebox.showinfo("Punkte", "In der aktuellen Liste sind keine Dateien vorhanden.")
            return
        if not messagebox.askyesno(
            "Punkte nachtragen",
            f"Für {len(upload_ids)} aktuell angezeigte Dateien fehlende automatische Punkte nachträglich ermitteln?\n\n"
            "Bereits vorhandene Punkte werden nicht doppelt gespeichert.",
        ):
            return
        try:
            resp = self.api.recalculate_points_bulk(self.api_token, upload_ids)
            processed = int(resp.get("processed", 0) or 0)
            eligible = int(resp.get("eligible", 0) or 0)
            created = int(resp.get("created", 0) or 0)
            skipped_existing = int(resp.get("skipped_existing", 0) or 0)
            skipped_ineligible = int(resp.get("skipped_ineligible", 0) or 0)
            messagebox.showinfo(
                "Punkte",
                "Nachberechnung abgeschlossen.\n\n"
                f"Geprüft: {processed}\n"
                f"Punkteberechtigt: {eligible}\n"
                f"Neu eingetragen: {created}\n"
                f"Bereits vorhanden: {skipped_existing}\n"
                f"Nicht punkteberechtigt: {skipped_ineligible}",
            )
            item = self.selected_admin_upload()
            if item and item.get("upload_id"):
                self.update_admin_document_points_display(str(item.get("upload_id")))
        except Exception as exc:
            messagebox.showerror("Punkte", str(exc))
            app_log_exception("Punkte-Nachberechnung für angezeigte Liste fehlgeschlagen", exc)

    def open_document_points_detail_dialog(self) -> None:
        item = self.selected_admin_upload()
        if not item or not item.get("upload_id"):
            messagebox.showwarning("Punkte", "Bitte zuerst ein Dokument auswählen.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkte ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkte des Dokuments")
        try: self.track_window_geometry(dialog, "Punkte des Dokuments")
        except Exception: pass
        dialog.geometry("900x480")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text=f"Dokument: {item.get('current_filename') or item.get('original_filename')}").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        tree = ttk.Treeview(dialog, columns=("date", "user", "cat", "reason", "points"), show="headings")
        for col, label, width in [("date", "Datum", 140), ("user", "Benutzer", 180), ("cat", "Kategorie", 120), ("reason", "Grund", 330), ("points", "Punkte", 70)]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns", pady=6)
        try:
            resp = self.api.document_points(self.api_token, str(item.get("upload_id")))
            for row in resp.get("points", []) or []:
                tree.insert("", "end", values=(row.get("created_at", ""), row.get("user_display_name", ""), row.get("category", ""), row.get("reason", ""), row.get("points", 0)))
        except Exception as exc:
            messagebox.showerror("Punkte", str(exc), parent=dialog)
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        if self.is_current_admin():
            ttk.Button(buttons, text="Sonderpunkte erfassen...", command=self.open_manual_points_dialog).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

    def show_selected_admin_details(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        # Bei Auswahl Details aus MySQL nachladen, damit Personen und Historie aktuell sind.
        api_item = self.api_get_document_item(str(item.get("upload_id", ""))) if self.api_token else None
        if api_item:
            # lokale JSON-Datei erhalten, falls der Datensatz aus dem Fallback stammt
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
            # Für das Auswahlfeld wird das passende Label aus der Benutzerliste gesetzt.
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
            self.new_status_var.set(item.get("status", "hochgeladen"))
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
                # Comboboxen mit readonly-Option behalten ihre Auswahllogik; normale Felder werden disabled.
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
        """Zielordner für Papierkorb-/Archivstatus unter 01_ABLAGE_ORTSCHRONIK."""
        status = (status or "").strip().lower()
        folder_name = {"archiviert": "ARCHIVIERT", "abgelehnt": "ABGELEHNT", "geloescht": "GELOESCHT"}.get(status)
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

    def move_linked_ocr_pdf_for_item(self, item: dict, new_document_path: Path) -> str:
        ocr_path = self.resolve_item_ocr_pdf_path(item)
        if not ocr_path:
            return ""
        target = new_document_path.with_name(f"{new_document_path.stem}_ocr.pdf")
        if ocr_path.resolve() == target.resolve():
            item["ocr_pdf_path"] = str(target)
            item["ocr_pdf_filename"] = target.name
            return ""
        target = unique_path_with_counter(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ocr_path), str(target))
        item["ocr_pdf_path"] = str(target)
        item["ocr_pdf_filename"] = target.name
        return f"; OCR-PDF: {ocr_path} → {target}"

    def move_admin_item_for_status(self, item: dict, old_status: str, new_status: str) -> tuple[bool, str]:
        """Verschiebt Dateien bei Status archiviert/abgelehnt/geloescht in den Ablage-Archivbereich.

        Archivieren ist nur erlaubt, wenn die Datei aktuell aus 01_ABLAGE_ORTSCHRONIK kommt.
        Reaktivierung auf erfasst versucht, den ursprünglichen Pfad wiederherzustellen.
        """
        new_status = (new_status or "").strip().lower()
        old_status = (old_status or "").strip().lower()
        current_path = self.resolve_document_local_path(item)
        if not current_path or not current_path.exists() or not current_path.is_file():
            return True, "Keine physische Datei verschoben."

        if new_status in {"archiviert", "abgelehnt", "geloescht"}:
            if new_status == "archiviert" and not self.is_path_under_named_folder(current_path, "01_ABLAGE_ORTSCHRONIK"):
                return False, "Archivieren ist nur für Dateien aus 01_ABLAGE_ORTSCHRONIK erlaubt."
            target_dir = self.status_archive_target(new_status)
            if target_dir is None:
                return True, ""
            target_dir.mkdir(parents=True, exist_ok=True)
            if not item.get("archived_from_path"):
                item["archived_from_path"] = str(current_path)
            target_path = unique_path_with_counter(target_dir / current_path.name)
            if target_path != current_path:
                shutil.move(str(current_path), str(target_path))
                item["current_filename"] = target_path.name
                item["current_path"] = str(target_path)
                item["target_folder"] = str(target_dir)
                ocr_msg = self.move_linked_ocr_pdf_for_item(item, target_path)
            else:
                ocr_msg = ""
            return True, f"Datei nach {target_dir.name} verschoben{ocr_msg}."

        if new_status == "erfasst" and old_status in {"archiviert", "abgelehnt", "geloescht"}:
            old_path_text = str(item.get("archived_from_path") or "").strip()
            if old_path_text:
                old_path = Path(old_path_text).expanduser()
                old_path.parent.mkdir(parents=True, exist_ok=True)
                target_path = unique_path_with_counter(old_path)
                if target_path != current_path:
                    shutil.move(str(current_path), str(target_path))
                    item["current_filename"] = target_path.name
                    item["current_path"] = str(target_path)
                    item["target_folder"] = str(target_path.parent)
                    self.move_linked_ocr_pdf_for_item(item, target_path)
                item["archived_from_path"] = ""
                return True, "Datei aus Archiv/Papierkorb reaktiviert."
            return True, "Kein ursprünglicher Pfad gespeichert; bitte Zielordner ggf. manuell wählen."
        return True, ""

    def admin_set_status(self, silent: bool = False) -> None:
        if not self.require_admin():
            return
        item = self.selected_admin_upload()
        if not item:
            if not silent:
                messagebox.showwarning("Keine Auswahl", "Bitte zuerst einen Upload auswählen.")
            return
        new_status = self.new_status_var.get().strip()
        old_status = item.get("status", "hochgeladen")
        if new_status == old_status:
            return
        display_name = self.display_name_var.get().strip() or "Admin"

        moved_ok, move_msg = self.move_admin_item_for_status(item, str(old_status), str(new_status))
        if not moved_ok:
            self.new_status_var.set(str(old_status))
            if not silent:
                messagebox.showwarning("Dokumentstatus", move_msg)
            return

        item["status"] = new_status
        details = f"{old_status} → {new_status}" + (f"; {move_msg}" if move_msg else "")
        append_metadata_history(item, display_name, "Dokumentstatus geändert", details, old_value=old_status, new_value=new_status)
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Dokumentstatus geändert", f"{item.get('upload_id')}: {details} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        if not silent:
            messagebox.showinfo("Dokumentstatus", "Dokumentstatus wurde gespeichert." if api_ok else f"Dokumentstatus lokal gespeichert; MySQL nicht aktualisiert:\n{api_msg}")

    def admin_rename_or_move(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst einen Upload auswählen.")
            return
        if not self.can_edit_admin_item(item):
            messagebox.showwarning("Keine Berechtigung", "Dieses Dokument kann nicht bearbeitet werden.")
            return
        if not self.is_current_admin():
            self.rename_own_pending_document(item)
            return

        self.normalize_admin_item_path_for_current_pc(item)
        current_path = self.resolve_document_local_path(item)
        if not current_path:
            messagebox.showerror("Fehler", "Die Datei konnte im lokalen Nextcloud-Stammverzeichnis nicht gefunden werden.")
            return
        if not current_path.exists():
            messagebox.showerror("Datei nicht gefunden", f"Die Datei wurde im Dateisystem nicht gefunden:\n{current_path}")
            return

        destination_folder_text = self.admin_destination_var.get().strip()
        destination_folder = getattr(self, "admin_destination_map", {}).get(destination_folder_text)
        if destination_folder is None:
            destination_folder = Path(destination_folder_text).expanduser() if destination_folder_text else current_path.parent
        requested_filename = self.admin_new_filename_var.get().strip() or current_path.name
        new_filename = make_normalized_archive_filename(item, requested_filename)
        destination_folder.mkdir(parents=True, exist_ok=True)
        candidate_path = destination_folder / new_filename
        new_path = candidate_path if candidate_path == current_path else unique_path_with_counter(candidate_path)
        self.admin_new_filename_var.set(new_path.name)

        if new_path == current_path:
            self.admin_save_metadata_fields(auto=True)
            messagebox.showinfo("Keine Dateiänderung", "Dateiname und Ordner sind unverändert. Metadaten wurden geprüft/gespeichert.")
            return

        confirm = messagebox.askyesno("Admin-Aktion bestätigen", f"Datei verschieben/umbenennen?\n\nVon:\n{current_path}\n\nNach:\n{new_path}\n\nDer Dateiname wurde normiert. Bei Namensgleichheit wird automatisch _#1, _#2 usw. ergänzt.")
        if not confirm:
            return

        try:
            shutil.move(str(current_path), str(new_path))
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        display_name = self.display_name_var.get().strip() or "Admin"
        old_value = str(current_path)
        new_value = str(new_path)
        item["current_filename"] = new_path.name
        item["current_path"] = str(new_path)
        item["target_folder"] = str(destination_folder)
        ocr_msg = self.move_linked_ocr_pdf_for_item(item, new_path)
        old_status = str(item.get("status", "") or "")
        item["status"] = "uebernommen"
        if hasattr(self, "new_status_var"):
            self.new_status_var.set("uebernommen")
        append_metadata_history(item, display_name, "Datei verschoben/umbenannt", f"{old_value} → {new_value}{ocr_msg}; Status: {old_status} → uebernommen", old_value=old_value, new_value=new_value)
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei verschoben/umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Admin", "Datei wurde verschoben/umbenannt und Metadaten wurden aktualisiert." if api_ok else f"Datei wurde lokal verschoben; MySQL nicht aktualisiert:\n{api_msg}")

    def rename_own_pending_document(self, item: dict) -> None:
        self.normalize_admin_item_path_for_current_pc(item)
        current_path = self.resolve_document_local_path(item)
        if not current_path or not current_path.exists():
            messagebox.showerror("Datei nicht gefunden", "Die Datei konnte lokal nicht gefunden werden.")
            return
        requested_filename = self.admin_new_filename_var.get().strip() or current_path.name
        new_filename = make_normalized_archive_filename(item, requested_filename)
        new_path = current_path.parent / new_filename
        if new_path != current_path:
            new_path = unique_path_with_counter(new_path)
        self.admin_new_filename_var.set(new_path.name)
        if new_path == current_path:
            self.admin_save_metadata_fields(auto=True)
            messagebox.showinfo("Keine Dateiänderung", "Dateiname ist unverändert. Metadaten wurden geprüft/gespeichert.")
            return
        if not messagebox.askyesno("Dateiname ändern", f"Datei umbenennen?\n\nVon:\n{current_path.name}\n\nNach:\n{new_path.name}"):
            return
        try:
            current_path.rename(new_path)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            return
        display_name = self.display_name_var.get().strip() or "Bearbeiter"
        old_value = str(current_path)
        new_value = str(new_path)
        item["current_filename"] = new_path.name
        item["current_path"] = str(new_path)
        item["target_folder"] = str(new_path.parent)
        ocr_msg = self.move_linked_ocr_pdf_for_item(item, new_path)
        append_metadata_history(item, display_name, "Datei umbenannt", f"{old_value} → {new_value}{ocr_msg}", old_value=old_value, new_value=new_value)
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        add_history(HistoryEntry.now(display_name, "Datei umbenannt", f"{old_value} → {new_value} | {api_msg}", item.get("upload_id")))
        self.refresh_history()
        self.refresh_admin_uploads(show_message=False)
        messagebox.showinfo("Dateiname", "Dateiname wurde gespeichert." if api_ok else f"Dateiname wurde lokal geändert; MySQL nicht aktualisiert:\n{api_msg}")


def main() -> None:
    if not acquire_single_instance_lock():
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                "ODV läuft bereits",
                "ODV ist bereits geöffnet oder wird gerade aktualisiert.\n\n"
                "Bitte warten Sie, bis das laufende Fenster geschlossen ist.",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
        return
    atexit.register(release_single_instance_lock)
    app = OrtschronikUploader()
    app.mainloop()


if __name__ == "__main__":
    main()
