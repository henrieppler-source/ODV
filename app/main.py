from __future__ import annotations

import shutil
import json
import hashlib
import re
import zipfile
import base64
import mimetypes
import unicodedata
import os
import platform
import subprocess
import webbrowser
import urllib.parse
import sys
import csv
import tempfile
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
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TK_BASE_CLASS = TkinterDnD.Tk
except Exception:  # Drag & Drop bleibt optional; ohne Bibliothek läuft ODV normal weiter.
    DND_FILES = None
    TkinterDnD = None
    TK_BASE_CLASS = tk.Tk

from .config import APP_DIR, load_config, save_config
from .database import init_db, add_history, list_history
from .users import (
    ROLES,
    load_users,
    save_users,
    find_user,
    find_user_by_username,
    normalize_username,
    hash_password,
    verify_password,
    role_allows_admin,
    role_allows_user_management,
)
from .file_service import (
    find_writable_folders,
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
from .upload_tab import UploadTabMixin
from PIL import Image, ImageTk, ImageDraw, ImageFont, ExifTags

APP_NAME = "Ortschronisten-Datei-Verwaltung"
APP_SHORT_NAME = "ODV"
APP_VERSION = "v110"

TRANSCRIPTION_TYPE_OPTIONS = [
    "",
    "kurze Transkription",
    "vollständige Transkription",
    "schwierige Handschrift",
    "Zeitung / Akte / Urkunde",
]

RIGHTS_NOTE_OPTIONS = [
    "",
    "A – frei nutzbar mit Namensnennung",
    "B – Nutzung nur nach Rücksprache",
    "C – nur interne Recherche - nicht veröffentlichen",
    "D – Rechte unklar",
]

DEFAULT_DOCUMENT_TYPE_OPTIONS = [
    "",
    "Bild",
    "PDF-Dokument",
    "Textdatei",
    "Tabellen-Datei",
    "Word-Dokument",
    "Video-Datei",
    "Audio-Datei",
    "Mehrere Dateien",
    "Sonstiges",
]

UPLOAD_REQUIRED_FIELDS = {"document_type", "current_filename", "uploaded_by", "uploaded_at", "document_date", "place", "description"}
UPLOAD_SIMPLE_FIELDS = {
    "document_type",
    "current_filename",
    "uploaded_by",
    "uploaded_at",
    "document_date",
    "place",
    "keywords",
}
METADATA_OPTION_KEYS = {
    "primary_source",
    "secondary_source",
    "original_location",
    "copyright_author",
    "rights_holder",
    "usage_permission",
    "license_note",
    "archive_name",
    "archive_signature",
}
FIELD_HELP_TEXTS = {
    "primary_source": "Direkte Herkunft, z. B. Fotoalbum Familie Müller, Original im Privatbesitz oder Vereinsarchiv.",
    "secondary_source": "Indirekte Quelle, z. B. Buch, Zeitung, Website, Datenbank oder mündlicher Hinweis.",
    "original_location": "Wo liegt das Original heute? Beispiel: Privatbesitz, Stadtarchiv, Vereinsarchiv.",
    "archive_name": "Name des Archivs oder Bestands, falls bekannt.",
    "archive_signature": "Archivsignatur, Aktenzeichen oder Inventarnummer.",
    "archive_accessed_at": "Datum des Abrufs oder der Einsichtnahme.",
    "copyright_author": "Wer hat Foto/Text/Scan erstellt, soweit bekannt.",
    "rights_holder": "Wer darf über die Nutzung entscheiden.",
    "usage_permission": "Kurz notieren, ob und wofür eine Nutzung erlaubt ist.",
    "license_note": "Lizenz, Sperrfrist oder Einschränkung, z. B. nur intern.",
    "rights_note": "Allgemeiner Rechtehinweis für spätere Veröffentlichung oder interne Nutzung.",
    "document_date": "Aufnahme-, Ereignis- oder Dokumentdatum. Auch Zeiträume sind möglich.",
    "place": "Ort oder, falls aus dem Bild übernommen, GPS-Koordinaten.",
    "keywords": "Mindestens 3 Stichwörter, getrennt durch Komma oder Semikolon.",
}

DEFAULT_MANUAL_BONUS_RULES = [
    ("manual_archive_research", "Recherche in Archiven", 0),
    ("manual_collection_indexing", "Erschließung von Beständen", 0),
    ("manual_event_organization", "Organisation Veranstaltung", 0),
    ("manual_excursion_organization", "Organisation Busfahrt / Exkursion", 0),
    ("manual_exhibition_work", "Mitarbeit an Ausstellung", 0),
    ("manual_digitization_support", "Digitalisierungshilfe", 0),
    ("manual_lecture_guided_tour", "Vortrag / Führung", 0),
    ("manual_other", "Sonstige Tätigkeit", 0),
]

VALID_POINT_RULES = [
    ("document_date", "Datum/Zeitraum angegeben", "metadata", "Datum / Zeitraum ist gefüllt"),
    ("event_topic", "Ereignis/Thema zugeordnet", "metadata", "Ereignis/Thema ist gefüllt"),
    ("metadata_description", "Aussagekräftige Beschreibung", "metadata", "Beschreibung ab Mindestlänge"),
    ("metadata_keywords", "Stichwörter vergeben", "metadata", "Mindestens 3 Stichwörter"),
    ("metadata_source", "Quelle/Herkunft angegeben", "metadata", "Primär- oder Sekundärquelle vorhanden"),
    ("openai_metadata", "OpenAI-Metadaten übernommen", "metadata", "Pauschale für übernommene OpenAI-Metadaten"),
    ("archive_signature", "Archivsignatur angegeben", "metadata", "Signaturfeld gefüllt"),
    ("rights_author", "Urheber angegeben", "metadata", "Urheberfeld gefüllt"),
    ("rights_holder", "Rechteinhaber angegeben", "metadata", "Rechteinhaber gefüllt"),
    ("rights_usage_permission", "Nutzungsfreigabe geklärt", "metadata", "Nutzungsfreigabe gefüllt"),
    ("rights_note", "Rechtehinweis angegeben", "metadata", "Rechtehinweis gefüllt"),
    ("transcription_short", "Kurze Transkription / Auszug", "metadata", "Transkription ja + Art kurz"),
    ("transcription_full", "Vollständige Transkription", "metadata", "Transkription ja + Art vollständig"),
    ("transcription_difficult", "Schwierige Handschrift / alte Schrift", "metadata", "Transkriptionsart schwierige Handschrift"),
    ("persons_marked", "Personen markiert", "persons", "Personenpunkte vorhanden"),
    ("persons_named", "Personen mit Namen versehen", "persons", "Personenmarkierungen mit Namen"),
    ("manual_archive_research", "Recherche in Archiven", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_collection_indexing", "Erschließung von Beständen", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_event_organization", "Organisation Veranstaltung", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_excursion_organization", "Organisation Busfahrt / Exkursion", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_exhibition_work", "Mitarbeit an Ausstellung", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_digitization_support", "Digitalisierungshilfe", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_lecture_guided_tour", "Vortrag / Führung", "manual", "Manuell vergebbare Sonderpunkte"),
    ("manual_other", "Sonstige Tätigkeit", "manual", "Manuell vergebbare Sonderpunkte"),
]


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None) -> None:
        if self.window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self.window = tk.Toplevel(self.widget)
            self.window.wm_overrideredirect(True)
            self.window.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(self.window, text=self.text, padding=6, relief="solid", borderwidth=1, wraplength=320)
            label.pack()
        except Exception:
            self.window = None

    def hide(self, _event=None) -> None:
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None



_SINGLE_INSTANCE_LOCK_HANDLE = None


def _odv_lock_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    lock_dir = root / "ODV"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "odv_app.lock"


def acquire_single_instance_lock() -> bool:
    """Verhindert, dass ODV versehentlich zweimal parallel läuft.

    Besonders wichtig beim Komfort-Updater: Die neue ODV darf erst starten,
    wenn die alte Instanz wirklich beendet ist. Unter Windows wird dafür eine
    echte Dateisperre verwendet; sie wird automatisch freigegeben, wenn der
    Prozess endet.
    """
    global _SINGLE_INSTANCE_LOCK_HANDLE
    if os.environ.get("ODV_DISABLE_SINGLE_INSTANCE") == "1":
        return True
    try:
        lock_path = _odv_lock_path()
        fh = open(lock_path, "a+", encoding="utf-8")
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                return False
        else:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                return False
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _SINGLE_INSTANCE_LOCK_HANDLE = fh
        return True
    except Exception:
        # Im Zweifel App nicht blockieren; der Updater hat zusätzlich Prozessschutz.
        return True


def release_single_instance_lock() -> None:
    global _SINGLE_INSTANCE_LOCK_HANDLE
    fh = _SINGLE_INSTANCE_LOCK_HANDLE
    if fh is None:
        return
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fh.close()
    except Exception:
        pass
    _SINGLE_INSTANCE_LOCK_HANDLE = None

def resource_path(relative_path: str) -> Path:
    """Pfad zu mitgelieferten Ressourcen, kompatibel mit PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path


class OrtschronikUploader(UploadTabMixin, TK_BASE_CLASS):
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

    def bind_global_mousewheel(self) -> None:
        """Mausrad soll in dem Bereich scrollen, über dem der Mauszeiger steht."""
        def scroll_widget(widget, delta: int):
            current = widget
            while current is not None:
                if hasattr(current, "yview"):
                    try:
                        current.yview_scroll(delta, "units")
                        return "break"
                    except Exception:
                        pass
                current = getattr(current, "master", None)
            return None

        def on_mousewheel(event):
            try:
                widget = self.winfo_containing(event.x_root, event.y_root)
                # Windows/macOS: delta > 0 bedeutet nach oben.
                delta = -1 if event.delta > 0 else 1
                return scroll_widget(widget, delta)
            except Exception:
                return None

        def on_button4(event):
            widget = self.winfo_containing(event.x_root, event.y_root)
            return scroll_widget(widget, -1)

        def on_button5(event):
            widget = self.winfo_containing(event.x_root, event.y_root)
            return scroll_widget(widget, 1)

        self.bind_all("<MouseWheel>", on_mousewheel, add="+")
        self.bind_all("<Button-4>", on_button4, add="+")
        self.bind_all("<Button-5>", on_button5, add="+")

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
        help_menu.add_command(label="Info", command=lambda: messagebox.showinfo(APP_NAME, f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION}\nNextcloud, API/MySQL\n(c) Henri Eppler, 2026"))
        help_menu.add_command(label="Systemstatus...", command=self.open_system_status_dialog)
        help_menu.add_command(label="Nach ODV-Update suchen...", command=lambda: self.check_app_update(interactive=True))
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.config(menu=menubar)

    def create_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("Dashboard.TFrame", background="#eeeeee")
        style.configure("Upload.TFrame", background="#eeeeee")
        style.configure("Viewer.TFrame", background="#eeeeee")
        style.configure("Admin.TFrame", background="#eeeeee")
        style.configure("Hint.TLabel", padding=2)
        try:
            default_font = tkfont.nametofont("TkDefaultFont")
            self.tab_font_normal = default_font.copy()
            self.tab_font_bold = default_font.copy()
            self.tab_font_bold.configure(weight="bold")
            style.map("TNotebook.Tab", font=[("selected", self.tab_font_bold), ("!selected", self.tab_font_normal)])
        except Exception:
            pass

    def update_tab_labels(self) -> None:
        if not hasattr(self, "notebook"):
            return
        names = {
            str(self.history_tab): "Dashboard",
            str(self.upload_tab_container): "Dateien hochladen",
            str(self.viewer_tab): "Dateien anzeigen",
            str(self.admin_tab): "Dateien bearbeiten",
        }
        try:
            selected = self.notebook.select()
            for tab_id in self.notebook.tabs():
                base = names.get(tab_id, self.notebook.tab(tab_id, "text").replace("● ", ""))
                self.notebook.tab(tab_id, text=("● " + base if tab_id == selected else "  " + base))
        except tk.TclError:
            pass

    def on_notebook_tab_changed(self, _event=None) -> None:
        self.update_tab_labels()
        self.update_connection_status()
        try:
            selected = self.notebook.select()
            if selected == str(self.history_tab):
                self.refresh_history()
            if selected == str(self.viewer_tab):
                self.refresh_file_view_folder_choices()
                self.refresh_file_view_tree()
                self.clear_file_view_selection()
            if selected == str(self.admin_tab) and self.is_current_admin():
                self.refresh_admin_uploads(show_message=False)
                self.clear_admin_selection()
        except Exception as exc:
            app_log_exception("Reiterwechsel konnte nicht vollständig verarbeitet werden", exc)

    def maximize_window(self) -> None:
        try:
            self.state("zoomed")  # Windows
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)  # manche Linux/Tk-Versionen
            except tk.TclError:
                pass

    def ui_settings(self) -> dict:
        data = self.config_data.setdefault("ui_settings", {})
        if not isinstance(data, dict):
            data = {}
            self.config_data["ui_settings"] = data
        return data

    def _window_state_key(self, key: str) -> str:
        text = str(key or "window").strip().lower()
        text = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")
        return text or "window"

    def _geometry_is_reasonable(self, geometry: str) -> bool:
        try:
            import re
            m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(geometry or ""))
            if not m:
                return False
            w, h, x, y = map(int, m.groups())
            if w < 300 or h < 180:
                return False
            sw = max(800, int(self.winfo_screenwidth() or 0))
            sh = max(600, int(self.winfo_screenheight() or 0))
            # Fenster darf nicht vollständig außerhalb des aktuellen Bildschirms liegen.
            if x > sw - 80 or y > sh - 80 or x < -max(200, w - 80) or y < -max(120, h - 80):
                return False
            return True
        except Exception:
            return False

    def restore_window_geometry(self, window: tk.Misc, key: str, default: str | None = None) -> None:
        try:
            k = self._window_state_key(key)
            geometry = str(self.ui_settings().get(k, {}).get("geometry", "") or "")
            if geometry and self._geometry_is_reasonable(geometry):
                window.geometry(geometry)
            elif default:
                window.geometry(default)
        except Exception as exc:
            app_log_exception("Fenstergeometrie konnte nicht wiederhergestellt werden", exc, key=key)

    def save_window_geometry(self, window: tk.Misc, key: str) -> None:
        try:
            if not bool(window.winfo_exists()):
                return
            k = self._window_state_key(key)
            geometry = window.winfo_geometry()
            if not self._geometry_is_reasonable(geometry):
                return
            settings = self.ui_settings().setdefault(k, {})
            settings["geometry"] = geometry
            save_config(self.config_data)
        except Exception:
            pass

    def track_window_geometry(self, window: tk.Misc, key: str, default: str | None = None) -> None:
        """Merkt Größe/Position eines Dialogs lokal je Gerät und stellt sie beim nächsten Öffnen wieder her.

        v81-Fix: In v80 wurde die Geometrie bei einigen Dialogen nicht zuverlässig gespeichert,
        weil das Speichern erst beim <Destroy>-Ereignis erfolgen sollte. Zu diesem Zeitpunkt liefert
        Tk je nach Dialog/Schließweg bereits keine belastbare Fenstergeometrie mehr. Deshalb wird
        die letzte sinnvolle Geometrie nun bereits bei Größen-/Positionsänderungen gepuffert und
        verzögert lokal gespeichert. Schließen per X und per Schließen-Button funktionieren dadurch
        gleichermaßen.
        """
        k = self._window_state_key(key)

        # Wiederherstellung erst nach dem Aufbau des Dialogs ausführen. Einige Dialoge setzen nach
        # track_window_geometry() noch eine Standardgröße; die verzögerte Wiederherstellung gewinnt
        # dann zuverlässig gegen diese Standardgröße.
        def _restore_later() -> None:
            try:
                self.restore_window_geometry(window, k, default)
            except Exception:
                pass

        try:
            window.after(120, _restore_later)
        except Exception:
            _restore_later()

        state = {"after_id": None, "last_geometry": ""}

        def _capture_geometry() -> str:
            try:
                if not bool(window.winfo_exists()):
                    return ""
                window.update_idletasks()
                geometry = str(window.winfo_geometry() or "")
                if self._geometry_is_reasonable(geometry):
                    state["last_geometry"] = geometry
                return state["last_geometry"]
            except Exception:
                return ""

        def _save_geometry_now() -> None:
            try:
                geometry = _capture_geometry()
                if not geometry:
                    return
                settings = self.ui_settings().setdefault(k, {})
                settings["geometry"] = geometry
                save_config(self.config_data)
            except Exception:
                pass

        def _schedule_save(event=None) -> None:
            try:
                if event is not None and event.widget is not window:
                    return
                _capture_geometry()
                old_after = state.get("after_id")
                if old_after:
                    try:
                        window.after_cancel(old_after)
                    except Exception:
                        pass
                state["after_id"] = window.after(500, _save_geometry_now)
            except Exception:
                pass

        def _close_window() -> None:
            _save_geometry_now()
            try:
                window.destroy()
            except Exception:
                pass

        def _save_on_destroy(event=None):
            try:
                if event is not None and event.widget is not window:
                    return
                _save_geometry_now()
            except Exception:
                pass

        try:
            window.bind("<Configure>", _schedule_save, add="+")
        except Exception:
            pass
        try:
            window.bind("<Destroy>", _save_on_destroy, add="+")
        except Exception:
            pass
        try:
            window.protocol("WM_DELETE_WINDOW", _close_window)
        except Exception:
            pass

    def on_main_window_close(self) -> None:
        self.save_window_geometry(self, "main_window")
        self.destroy()

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

    def create_history_tab(self) -> None:
        self.history_tab.columnconfigure(0, weight=1)
        self.history_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.history_tab)
        top.grid(row=0, column=0, sticky="ew")
        self.history_scope_var = tk.StringVar(value=self.config_data.get("history_scope", "all"))
        ttk.Radiobutton(top, text="Alle Aktionen", variable=self.history_scope_var, value="all", command=self.refresh_history).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(top, text="Nur eigene Aktionen", variable=self.history_scope_var, value="own", command=self.refresh_history).pack(side="left", padx=(0, 20))
        try:
            self.history_scope_var.trace_add("write", lambda *_: self.after_idle(self.refresh_history))
        except Exception:
            pass

        table_frame = ttk.Frame(self.history_tab)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=8)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.history_tree = ttk.Treeview(table_frame, columns=("time", "user", "action", "details"), show="headings")
        configured_widths = self.config_data.get("tree_column_widths", {}).get("history", {})
        for col, label, width in [
            ("time", "Zeitpunkt", 150),
            ("user", "Benutzer", 180),
            ("action", "Aktion", 170),
            ("details", "Details", 650),
        ]:
            self.history_tree.heading(col, text=label, anchor="w")
            self.history_tree.column(col, width=int(configured_widths.get(col, width)), anchor="w")
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        history_vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_tree.yview)
        history_hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=history_vsb.set, xscrollcommand=history_hsb.set)
        history_vsb.grid(row=0, column=1, sticky="ns")
        history_hsb.grid(row=1, column=0, sticky="ew")
        self.history_tree.bind("<ButtonRelease-1>", lambda _e: self.save_tree_column_widths(silent=True))
        self.history_tree.bind("<Double-1>", lambda _e: self.show_history_metadata_details())

    def document_type_options(self) -> list[str]:
        values = list(DEFAULT_DOCUMENT_TYPE_OPTIONS)
        for dt in self.config_data.get("document_type_options", []) or []:
            text = str(dt or "").strip()
            if text and text not in values:
                values.append(text)
        return values

    def remember_document_type(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        values = self.document_type_options()
        if text not in values:
            values.append(text)
            self.config_data["document_type_options"] = values
            save_config(self.config_data)
        self.update_document_type_comboboxes()

    def update_document_type_comboboxes(self) -> None:
        values = self.document_type_options()
        for name in ("upload_document_type_combo", "admin_document_type_combo"):
            widget = getattr(self, name, None)
            if widget is not None:
                try:
                    widget["values"] = values
                except Exception:
                    pass

    def archive_collection_options(self, limit: int | None = None) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for text in self.config_data.get("archive_collection_options", []) or []:
            value = str(text or "").strip()
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                values.append(value)
        for text in self.metadata_value_options("archive_name", limit=500):
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                values.append(text)
        values.sort(key=str.casefold)
        return values[:limit] if limit else values

    def remember_archive_collection(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        values = self.archive_collection_options()
        if text.casefold() not in {v.casefold() for v in values}:
            values.append(text)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            save_config(self.config_data)
        self.refresh_upload_metadata_option_comboboxes()

    def metadata_value_options(self, key: str, limit: int = 10) -> list[str]:
        counts: dict[str, int] = {}
        try:
            items = load_metadata_files(self.metadata_folder_path())
        except Exception:
            items = []
        aliases = {
            "primary_source": ["primary_source", "primaerquelle"],
            "secondary_source": ["secondary_source", "sekundaerquelle", "source", "quelle"],
            "copyright_author": ["copyright_author", "urheber"],
            "rights_holder": ["rights_holder", "rechteinhaber"],
            "usage_permission": ["usage_permission", "nutzungsfreigabe"],
            "license_note": ["license_note", "lizenz"],
            "rights_note": ["rights_note", "rechte"],
            "archive_name": ["archive_name", "archiv"],
            "archive_signature": ["archive_signature", "signatur"],
            "original_location": ["original_location", "standort_original"],
        }.get(key, [key])
        for item in items:
            for alias in aliases:
                text = str(item.get(alias) or "").strip()
                if text:
                    counts[text] = counts.get(text, 0) + 1
        if key == "archive_name":
            configured = {text.casefold(): text for text in self.config_data.get("archive_collection_options", []) or [] if str(text or "").strip()}
            for text in configured.values():
                counts.setdefault(text, 0)
            return [text for text, _count in sorted(counts.items(), key=lambda x: x[0].casefold())[:limit]]
        return [text for text, _count in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))[:limit]]

    def refresh_upload_metadata_option_comboboxes(self) -> None:
        for key, widget in getattr(self, "upload_option_comboboxes", {}).items():
            try:
                widget.configure(values=(self.archive_collection_options() if key == "archive_name" else self.metadata_value_options(key)))
            except Exception:
                pass

    def add_field_tooltip(self, label_widget: tk.Widget, key: str) -> None:
        text = FIELD_HELP_TEXTS.get(key, "")
        if text:
            ToolTip(label_widget, text)

    def exif_gps_decimal(self, values) -> float | None:
        try:
            parts = []
            for v in values:
                if hasattr(v, "numerator") and hasattr(v, "denominator"):
                    parts.append(float(v.numerator) / float(v.denominator))
                elif isinstance(v, tuple) and len(v) == 2:
                    parts.append(float(v[0]) / float(v[1]))
                else:
                    parts.append(float(v))
            return parts[0] + parts[1] / 60 + parts[2] / 3600
        except Exception:
            return None

    def image_metadata_suggestions(self, path: Path) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        if not is_image_file(path):
            return suggestions
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                if not exif:
                    return suggestions
                tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
                date_text = str(tag_map.get("DateTimeOriginal") or tag_map.get("DateTimeDigitized") or tag_map.get("DateTime") or "").strip()
                if date_text:
                    suggestions["document_date"] = date_text.replace(":", "-", 2)
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else {}
                if gps_ifd:
                    gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                    lat = self.exif_gps_decimal(gps.get("GPSLatitude"))
                    lon = self.exif_gps_decimal(gps.get("GPSLongitude"))
                    if lat is not None and lon is not None:
                        if str(gps.get("GPSLatitudeRef", "")).upper() == "S":
                            lat *= -1
                        if str(gps.get("GPSLongitudeRef", "")).upper() == "W":
                            lon *= -1
                        suggestions["place"] = f"{lat:.6f}, {lon:.6f}"
        except Exception as exc:
            app_log_exception("EXIF-Metadaten konnten nicht gelesen werden", exc, path=str(path))
        return suggestions

    def apply_image_metadata_suggestions(self, path: Path) -> None:
        suggestions = self.image_metadata_suggestions(path)
        for key, value in suggestions.items():
            var = self.meta_vars.get(key) if hasattr(self, "meta_vars") else None
            if var is not None and not str(var.get() or "").strip():
                var.set(value)

    def refresh_document_type_options_from_documents(self, docs: list[dict]) -> None:
        changed = False
        values = self.document_type_options()
        for doc in docs:
            text = str(doc.get("document_type") or "").strip()
            if text and text not in values:
                values.append(text)
                changed = True
        if changed:
            self.config_data["document_type_options"] = values
            save_config(self.config_data)
            self.update_document_type_comboboxes()


    def description_char_count_text(self, widget: tk.Text) -> str:
        try:
            count = len(widget.get("1.0", "end-1c").strip())
        except Exception:
            count = 0
        suffix = " – punktefähig" if count >= 50 else ""
        return f"Zeichen: {count} / 50{suffix}"

    def update_description_counter(self, widget: tk.Text, label_var: tk.StringVar) -> None:
        label_var.set(self.description_char_count_text(widget))

    def make_scrolled_text(self, parent, height: int = 4, wrap: str = "word") -> tuple[tk.Text, ttk.Frame]:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        txt = tk.Text(frame, height=height, wrap=wrap, undo=True)
        vbar = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        hbar = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        txt.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        if wrap == "none":
            hbar.grid(row=1, column=0, sticky="ew")
        return txt, frame

    def create_metadata_form_two_columns(self, parent: tk.Widget, target: str) -> dict[str, object]:
        """Erzeugt ein zweispaltiges Metadatenformular.

        target = "file_view", "admin" oder "upload". Die Rückgabe enthält Variablen,
        Textfelder und Widgets zur späteren Befüllung/Sperrung.
        """
        result: dict[str, object] = {"vars": {}, "widgets": [], "advanced_widgets": []}
        for c in (1, 3):
            parent.columnconfigure(c, weight=1, uniform=f"{target}_meta")

        row_offset = 1 if target == "upload" else 0
        sections = [
            (row_offset + 0, 0, "Technische Daten", [
                ("Upload-ID", "upload_id"),
                ("Dokumenttyp", "document_type"),
                ("Status", "status"),
                ("Aktueller Dateiname", "current_filename"),
                ("Erfasst von", "uploaded_by"),
                ("Hochgeladen am", "uploaded_at"),
            ]),
            (row_offset + 0, 2, "Quelle / Herkunft", [
                ("Primärquelle", "primary_source"),
                ("Sekundärquelle", "secondary_source"),
                ("Standort Original", "original_location"),
                ("Archiv", "archive_name"),
                ("Signatur", "archive_signature"),
                ("Abruf am", "archive_accessed_at"),
                ("Transkription", "_transcription_combined"),
            ]),
            (row_offset + 8, 0, "Zeit / Ort / Inhalt", [
                ("Datum / Zeitraum", "document_date"),
                ("Ereignis", "event"),
                ("Ort", "place"),
                ("Stichwörter", "keywords"),
            ]),
            (row_offset + 8, 2, "Rechte", [
                ("Urheber/in", "copyright_author"),
                ("Rechteinhaber", "rights_holder"),
                ("Nutzungsfreigabe", "usage_permission"),
                ("Lizenz / Einschränkungen", "license_note"),
                ("Rechte / Nutzung allgemein", "rights_note"),
            ]),
        ]
        all_vars: dict[str, tk.Variable] = result["vars"]  # type: ignore[assignment]
        widgets: list[tk.Widget] = result["widgets"]  # type: ignore[assignment]
        advanced_widgets: list[tk.Widget] = result["advanced_widgets"]  # type: ignore[assignment]
        max_row = 0
        for row0, col0, heading, fields in sections:
            heading_widget = ttk.Label(parent, text=heading, font=("", 10, "bold"))
            heading_widget.grid(row=row0, column=col0, columnspan=2, sticky="w", pady=(8, 3), padx=(0 if col0 == 0 else 18, 4))
            if target == "upload" and all(key not in UPLOAD_SIMPLE_FIELDS for _label, key in fields):
                advanced_widgets.append(heading_widget)
            row = row0 + 1
            for label, key in fields:
                label_text = f"{label}{' *' if target == 'upload' and key in UPLOAD_REQUIRED_FIELDS else ''}:"
                label_widget = ttk.Label(parent, text=label_text)
                label_widget.grid(row=row, column=col0, sticky="w", pady=2, padx=(0 if col0 == 0 else 18, 4))
                if target == "upload":
                    self.add_field_tooltip(label_widget, key)
                    if key not in UPLOAD_SIMPLE_FIELDS:
                        advanced_widgets.append(label_widget)
                if key == "_transcription_combined":
                    trans_frame = ttk.Frame(parent)
                    trans_frame.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    done_var = tk.BooleanVar(value=False)
                    type_var = tk.StringVar()
                    all_vars["transcription_done"] = done_var
                    all_vars["transcription_type"] = type_var
                    check = ttk.Checkbutton(trans_frame, text="ja", variable=done_var)
                    check.pack(side="left")
                    ttk.Label(trans_frame, text="Art:").pack(side="left", padx=(16, 4))
                    combo = ttk.Combobox(trans_frame, textvariable=type_var, values=TRANSCRIPTION_TYPE_OPTIONS, width=28, state="readonly")
                    combo.pack(side="left")
                    if target == "file_view":
                        check.configure(command=lambda: self.save_file_view_metadata(auto=True))
                        combo.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        check.configure(command=lambda: self.admin_save_metadata_fields(auto=True))
                        combo.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                    widgets.extend([check, combo])
                    if target == "upload":
                        advanced_widgets.append(trans_frame)
                    row += 1
                    continue
                elif key == "uploaded_by" and target in {"admin", "file_view", "upload"}:
                    var = tk.StringVar()
                    all_vars[key] = var
                    if target == "admin":
                        widget = ttk.Combobox(parent, textvariable=var, values=[], width=32, state="readonly")
                        self.admin_uploaded_by_combo = widget
                        self.admin_uploaded_by_user_map = {}
                        widget.bind("<<ComboboxSelected>>", self.admin_uploaded_by_changed)
                    elif target == "file_view":
                        widget = ttk.Combobox(parent, textvariable=var, values=[], width=32, state="readonly")
                        self.file_view_uploaded_by_combo = widget
                        self.file_view_uploaded_by_user_map = {}
                        widget.bind("<<ComboboxSelected>>", self.file_view_uploaded_by_changed)
                    else:
                        widget = ttk.Entry(parent, textvariable=var, state="disabled")
                    widget.grid(row=row, column=col0 + 1, sticky="ew", padx=6, pady=2)
                elif key == "document_type":
                    var = tk.StringVar()
                    all_vars[key] = var
                    widget = ttk.Combobox(parent, textvariable=var, values=self.document_type_options(), width=28, state="normal")
                    widget.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                        widget.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        self.admin_document_type_combo = widget
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                        widget.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
                    else:
                        self.upload_document_type_combo = widget
                elif key == "rights_note":
                    var = tk.StringVar()
                    all_vars[key] = var
                    widget_state = "normal" if target == "upload" else "readonly"
                    widget = ttk.Combobox(parent, textvariable=var, values=RIGHTS_NOTE_OPTIONS, width=42, state=widget_state)
                    widget.grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        widget.bind("<<ComboboxSelected>>", lambda _e: self.admin_save_metadata_fields(auto=True))
                else:
                    var = tk.StringVar()
                    all_vars[key] = var
                    state = "disabled" if target == "upload" and key in {"upload_id", "status", "current_filename", "uploaded_at"} else "normal"
                    if target == "upload" and key in METADATA_OPTION_KEYS:
                        widget = ttk.Combobox(parent, textvariable=var, values=self.metadata_value_options(key), state="normal")
                        self.upload_option_comboboxes = getattr(self, "upload_option_comboboxes", {})
                        self.upload_option_comboboxes[key] = widget
                    else:
                        widget = ttk.Entry(parent, textvariable=var, state=state)
                    widget.grid(row=row, column=col0 + 1, sticky="ew", padx=6, pady=2)
                    if target == "file_view":
                        widget.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
                    elif target == "admin":
                        widget.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
                widgets.append(widget)
                if target == "upload" and key not in UPLOAD_SIMPLE_FIELDS:
                    advanced_widgets.append(widget)
                row += 1
                if key == "keywords":
                    ttk.Label(
                        parent,
                        text="Für Punkte: mindestens 3 Stichwörter, getrennt durch Komma oder Semikolon.",
                        foreground="#555555",
                    ).grid(row=row, column=col0 + 1, sticky="w", padx=6, pady=(0, 3))
                    row += 1
            max_row = max(max_row, row)

        row = max_row + 1
        desc_label = ttk.Label(parent, text=f"Beschreibung{' *' if target == 'upload' else ''}:")
        desc_label.grid(row=row, column=0, sticky="nw", pady=2)
        desc_text, desc_frame = self.make_scrolled_text(parent, height=4, wrap="word")
        desc_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=6, pady=2)
        widgets.append(desc_text)
        desc_counter_var = tk.StringVar(value=self.description_char_count_text(desc_text))
        desc_text.bind("<KeyRelease>", lambda _e, w=desc_text, v=desc_counter_var: self.update_description_counter(w, v), add="+")
        row += 1
        ttk.Label(parent, textvariable=desc_counter_var, foreground="#555555").grid(row=row, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 0))
        row += 1
        ttk.Label(parent, text="Für Punkte: mindestens 50 Zeichen.", foreground="#555555").grid(row=row, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 3))
        row += 1
        note_label = ttk.Label(parent, text="Bemerkung:")
        note_label.grid(row=row, column=0, sticky="nw", pady=2)
        note_text, note_frame = self.make_scrolled_text(parent, height=3, wrap="word")
        note_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=6, pady=2)
        widgets.append(note_text)
        if target == "upload":
            advanced_widgets.extend([note_label, note_frame])
        row += 1
        json_label = ttk.Label(parent, text="Metadaten / Historie:")
        json_label.grid(row=row, column=0, sticky="nw", pady=2)
        json_text, json_frame = self.make_scrolled_text(parent, height=8, wrap="none")
        json_frame.grid(row=row, column=1, columnspan=3, sticky="nsew", padx=6, pady=2)
        small_font = tkfont.nametofont("TkDefaultFont").copy()
        try:
            small_font.configure(size=max(7, small_font.cget("size") - 1))
        except Exception:
            pass
        json_text.configure(state="disabled", font=small_font)
        parent.rowconfigure(row, weight=1)
        if target == "upload":
            advanced_widgets.extend([json_label, json_frame])

        if target == "file_view":
            desc_text.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
            note_text.bind("<FocusOut>", lambda _e: self.save_file_view_metadata(auto=True))
            ttk.Button(parent, text="Metadaten speichern", command=lambda: self.save_file_view_metadata(auto=False)).grid(row=row + 1, column=1, sticky="w", padx=6, pady=6)
        elif target == "admin":
            desc_text.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
            note_text.bind("<FocusOut>", lambda _e: self.admin_save_metadata_fields(auto=True))
            ttk.Button(parent, text="Metadaten speichern", command=lambda: self.admin_save_metadata_fields(auto=False)).grid(row=row + 1, column=3, sticky="e", padx=6, pady=6)
        else:
            json_text.configure(state="normal")
            json_text.delete("1.0", "end")
            json_text.insert("1.0", "Upload-ID und Historie werden beim Hochladen angelegt.")
            json_text.configure(state="disabled")

        result["description_text"] = desc_text
        result["description_counter_var"] = desc_counter_var
        result["note_text"] = note_text
        result["json_text"] = json_text
        return result

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

    def load_email_users(self) -> list[dict]:
        """Aktive Benutzer mit E-Mail-Adresse aus der API laden."""
        if not self.api_token:
            return []
        try:
            response = self.api.list_users(self.api_token)
            users = []
            for user in response.get("users", []):
                if int(user.get("is_active", 0) or 0) != 1:
                    continue
                email = str(user.get("email", "") or "").strip()
                if not email:
                    continue
                users.append(user)
            return users
        except Exception as exc:
            app_log_exception("E-Mail-Benutzer konnten nicht geladen werden", exc)
            return []

    def load_mail_groups(self) -> list[dict]:
        if not self.api_token:
            return []
        try:
            response = self.api.list_mail_groups(self.api_token)
            return list(response.get("groups", []))
        except Exception as exc:
            app_log_exception("Verteiler konnten nicht geladen werden", exc)
            return []


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

    def format_mail_history_detail(self, item: dict) -> str:
        """Lesbare Detailansicht für Versandhistorie statt Roh-JSON."""
        docs = item.get("documents") or item.get("links") or item.get("document_links") or ""
        if isinstance(docs, str):
            try:
                parsed = json.loads(docs)
                docs = parsed
            except Exception:
                pass
        lines = [
            "Versanddetails",
            "---------------",
            f"Zeitpunkt: {item.get('sent_at') or item.get('created_at') or ''}",
            f"Versendet von: {item.get('sender_name') or item.get('sent_by_name') or ''}",
            f"Empfänger: {item.get('recipient_email') or item.get('recipient') or ''}",
            f"Betreff: {item.get('subject') or ''}",
            f"Versandart: {item.get('mode') or item.get('send_mode') or ''}",
            f"Status: {item.get('status') or ''}",
            "",
            "Mailtext",
            "--------",
            str(item.get('body_preview') or item.get('body') or item.get('message') or '').replace('\\n', '\n'),
            "",
            "Dokumente / Links",
            "-----------------",
        ]
        if isinstance(docs, (list, tuple)):
            for i, d in enumerate(docs, 1):
                if isinstance(d, dict):
                    label = d.get('file') or d.get('filename') or d.get('name') or ''
                    link = d.get('link') or d.get('download_url') or d.get('url') or ''
                    lines.append(f"{i}. Datei: {label}")
                    if link:
                        lines.append(f"   Link: {link}")
                else:
                    lines.append(f"{i}. {d}")
        elif docs:
            lines.append(str(docs))
        else:
            lines.append("Keine Dokumente/Links gespeichert.")
        if item.get('error') or item.get('error_message'):
            lines += ["", "Fehlerstatus", "------------", str(item.get('error') or item.get('error_message'))]
        return "\n".join(lines)

    def open_mail_history_dialog(self) -> None:
        """Zeigt die serverseitige Historie der über ODV versendeten Rundmails."""
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Die Versandhistorie ist Admins und Superadmins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Versandhistorie")
        try: self.track_window_geometry(dialog, "Versandhistorie")
        except Exception: pass
        dialog.geometry("1180x700")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text="Welche Rundmail ging wann an wen? Die Historie wird serverseitig gespeichert.", wraplength=1100).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        pane = ttk.PanedWindow(dialog, orient=tk.VERTICAL)
        pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        table_frame = ttk.Frame(pane)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        detail_frame = ttk.Frame(pane)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        cols = ("sent_at", "sender", "recipient", "subject", "mode", "status", "documents")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headers = {
            "sent_at": ("Zeitpunkt", 155), "sender": ("Versendet von", 170), "recipient": ("Empfänger", 220),
            "subject": ("Betreff", 260), "mode": ("Art", 100), "status": ("Status", 100), "documents": ("Dokumente/Links", 480),
        }
        for col, (label, width) in headers.items():
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w", stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")
        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        detail = tk.Text(detail_frame, height=10, wrap="none")
        detail.grid(row=0, column=0, sticky="nsew")
        detail_y = ttk.Scrollbar(detail_frame, orient="vertical", command=detail.yview)
        detail_x = ttk.Scrollbar(detail_frame, orient="horizontal", command=detail.xview)
        detail.configure(yscrollcommand=detail_y.set, xscrollcommand=detail_x.set)
        detail_y.grid(row=0, column=1, sticky="ns")
        detail_x.grid(row=1, column=0, sticky="ew")
        detail.configure(state="disabled")
        pane.add(table_frame, weight=3)
        pane.add(detail_frame, weight=1)
        rows: list[dict] = []
        def load() -> None:
            nonlocal rows
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.mail_history(self.api_token, limit=500)
                rows = list(resp.get("items", []) or resp.get("history", []) or [])
            except ApiError as exc:
                messagebox.showerror("Versandhistorie", f"Versandhistorie konnte nicht geladen werden:\n{exc}", parent=dialog)
                return
            for i, item in enumerate(rows):
                docs = item.get("documents") or item.get("links") or ""
                if isinstance(docs, (list, tuple)):
                    docs = "; ".join(str(x) for x in docs)
                tree.insert("", "end", iid=str(i), values=(
                    item.get("sent_at") or item.get("created_at") or "",
                    item.get("sender_name") or item.get("sent_by_name") or "",
                    item.get("recipient_email") or item.get("recipient") or "",
                    item.get("subject") or "",
                    item.get("mode") or item.get("send_mode") or "",
                    item.get("status") or "",
                    str(docs or "")[:500],
                ))
        def show_detail(_event=None) -> None:
            sel = tree.selection()
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            if sel:
                try:
                    item = rows[int(sel[0])]
                    detail.insert("1.0", self.format_mail_history_detail(item))
                except Exception:
                    pass
            detail.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", show_detail)
        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Aktualisieren", command=load).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
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

    def open_system_status_dialog(self) -> None:
        """Zeigt den ausführlichen Betriebsstatus auf Wunsch über das Hilfe-Menü."""
        try:
            lines = self.startup_system_check_lines()
            dialog = tk.Toplevel(self)
            dialog.title("ODV-Systemstatus")
            try: self.track_window_geometry(dialog, "ODV-Systemstatus")
            except Exception: pass
            dialog.transient(self)
            dialog.resizable(True, True)
            dialog.columnconfigure(0, weight=1)
            dialog.rowconfigure(0, weight=1)
            frame = ttk.Frame(dialog, padding=14)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            ttk.Label(frame, text="Systemstatus", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
            text = tk.Text(frame, width=92, height=min(18, max(8, len(lines)+1)), wrap="word")
            text.grid(row=1, column=0, sticky="nsew")
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")
            buttons = ttk.Frame(frame)
            buttons.grid(row=2, column=0, sticky="e", pady=(8, 0))
            ttk.Button(buttons, text="Aktualisieren", command=lambda: self.refresh_system_status_text(text)).pack(side="left", padx=4)
            ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
            dialog.update_idletasks()
            x = self.winfo_rootx() + max(60, (self.winfo_width() - dialog.winfo_width()) // 2)
            y = self.winfo_rooty() + 80
            dialog.geometry(f"+{x}+{y}")
        except Exception as exc:
            app_log_exception("Systemstatus konnte nicht angezeigt werden", exc)

    def refresh_system_status_text(self, text: tk.Text) -> None:
        lines = self.startup_system_check_lines()
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")


    def parse_version_number(self, version: str) -> int:
        """Extrahiert die führende ODV-Versionsnummer aus Strings wie v69."""
        text = str(version or "").strip().lower().lstrip("v")
        digits = "".join(ch for ch in text if ch.isdigit())
        try:
            return int(digits or 0)
        except Exception:
            return 0

    def is_newer_version(self, remote_version: str, local_version: str = APP_VERSION) -> bool:
        return self.parse_version_number(remote_version) > self.parse_version_number(local_version)

    def get_app_update_info(self) -> dict:
        """Liest die freigegebene App-Version aus der API."""
        try:
            resp = self.api.app_update(self.api_token or None)
            info = resp.get("update") or resp.get("release") or resp
            return info if isinstance(info, dict) else {}
        except Exception:
            raise

    def default_update_target_dir(self, version: str) -> Path:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return root / "ODV" / "versions" / str(version).strip()

    def update_attempt_marker_path(self) -> Path:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return root / "ODV" / "updates" / "last_update_attempt.json"

    def write_update_attempt_marker(self, update: dict, source_dir: Path, target_dir: Path) -> None:
        """Merkt sich einen gestarteten Updateversuch, damit eine fehlgeschlagene Installation keine Endlosschleife auslöst."""
        try:
            marker = self.update_attempt_marker_path()
            marker.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "from_version": APP_VERSION,
                "to_version": str(update.get("version") or ""),
                "file_name": str(update.get("file_name") or update.get("file") or ""),
                "source_dir": str(source_dir),
                "target_dir": str(target_dir),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            }
            marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def read_update_attempt_marker(self) -> dict:
        try:
            marker = self.update_attempt_marker_path()
            if marker.exists():
                data = json.loads(marker.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def has_recent_update_attempt(self, latest_version: str, max_minutes: int = 30) -> bool:
        """Verhindert Update-Endlosschleifen nach einem fehlgeschlagenen oder unvollständigen Selbstupdate."""
        data = self.read_update_attempt_marker()
        if str(data.get("to_version") or "").strip() != str(latest_version or "").strip():
            return False
        started = str(data.get("started_at") or "")
        try:
            dt = datetime.fromisoformat(started)
            age = (datetime.now() - dt).total_seconds() / 60.0
            return 0 <= age <= max_minutes
        except Exception:
            return True

    def resolve_nextcloud_update_source(self, update: dict) -> Path | None:
        """Ermittelt die lokale Nextcloud-Quelle der freigegebenen Update-Datei."""
        base_text = self.base_folder_var.get().strip() if hasattr(self, "base_folder_var") else ""
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        rel = str(update.get("nextcloud_relative_path") or update.get("path") or update.get("file_path") or "").strip()
        file_name = str(update.get("file_name") or update.get("file") or "").strip()
        candidates: list[Path] = []
        if rel:
            rel_path = Path(rel.replace("/", os.sep).replace("\\", os.sep))
            candidates.append(base / rel_path)
            if file_name and rel_path.name.lower() != file_name.lower():
                candidates.append(base / rel_path / file_name)
        if file_name:
            candidates.append(base / "02_AUSTAUSCH" / "ODV_UPDATE" / "Windows" / file_name)
            candidates.append(base / "02_AUSTAUSCH" / "ODV_UPDATE" / file_name)
            candidates.append(base / "AUSTAUSCH" / "ODV_UPDATE" / "Windows" / file_name)
            candidates.append(base / "AUSTAUSCH" / "ODV_UPDATE" / file_name)
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    return candidate
            except Exception:
                pass
        return None

    def sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def stage_app_update(self, update: dict) -> Path:
        """Kopiert/entpackt die freigegebene Version aus dem lokalen Nextcloud-Syncordner."""
        version = str(update.get("version") or "").strip()
        if not version:
            raise RuntimeError("Die Updatefreigabe enthält keine Versionsnummer.")
        source = self.resolve_nextcloud_update_source(update)
        if not source:
            raise RuntimeError("Die freigegebene Update-Datei wurde im lokalen Nextcloud-Ordner nicht gefunden. Bitte Nextcloud-Sync prüfen.")
        expected_hash = str(update.get("sha256") or "").strip().lower()
        if expected_hash:
            actual_hash = self.sha256_file(source).lower()
            if actual_hash != expected_hash:
                raise RuntimeError("Die Prüfsumme der Update-Datei stimmt nicht. Update wird nicht installiert.")
        target_dir = self.default_update_target_dir(version)
        target_dir.mkdir(parents=True, exist_ok=True)
        staged_file = target_dir / source.name
        shutil.copy2(source, staged_file)
        if expected_hash:
            staged_hash = self.sha256_file(staged_file).lower()
            if staged_hash != expected_hash:
                raise RuntimeError("Die kopierte Update-Datei ist fehlerhaft. Prüfsumme stimmt nicht.")
        if staged_file.suffix.lower() == ".zip":
            extract_dir = target_dir / "entpackt"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_file, "r") as zf:
                zf.extractall(extract_dir)
            exe_matches = list(extract_dir.rglob("ODV.exe")) + list(extract_dir.rglob("*.exe"))
            return exe_matches[0] if exe_matches else extract_dir
        return staged_file

    def current_install_dir(self) -> Path:
        """Ermittelt den Programmordner, der vom Komfort-Updater ersetzt werden soll."""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    def find_updater_executable(self) -> Path | None:
        """Sucht die mitgelieferte ODV_Updater.exe bzw. das Python-Updaterscript im Entwicklungsmodus."""
        install_dir = self.current_install_dir()
        candidates = [
            install_dir / "ODV_Updater.exe",
            install_dir / "updater" / "ODV_Updater.exe",
            Path(sys.executable).resolve().parent / "ODV_Updater.exe" if getattr(sys, "frozen", False) else None,
        ]
        for candidate in candidates:
            if candidate and candidate.exists() and candidate.is_file():
                return candidate
        dev_script = Path(__file__).resolve().parent.parent / "launcher_updater.py"
        if dev_script.exists():
            return dev_script
        return None

    def resolve_prepared_update_root(self, prepared: Path) -> Path:
        """Ermittelt aus stage_app_update() den Quellordner, aus dem die neue Version kopiert wird."""
        prepared = Path(prepared)
        if prepared.is_file():
            # Wenn eine EXE gefunden wurde, soll der ganze zugehörige Programmordner kopiert werden.
            if prepared.name.lower() == "odv.exe":
                return prepared.parent
            return prepared.parent
        return prepared

    def launch_comfort_updater(self, prepared: Path, update: dict) -> None:
        """Startet den separaten Komfort-Updater und beendet die laufende ODV-Instanz."""
        updater = self.find_updater_executable()
        if not updater:
            raise RuntimeError("ODV_Updater.exe wurde nicht gefunden. Bitte Buildpaket vollständig verteilen.")

        source_dir = self.resolve_prepared_update_root(Path(prepared)).resolve()
        target_dir = self.current_install_dir().resolve()
        if not source_dir.exists():
            raise RuntimeError("Der vorbereitete Updateordner wurde nicht gefunden.")
        if not target_dir.exists():
            raise RuntimeError("Der aktuelle Programmordner wurde nicht gefunden.")
        if source_dir == target_dir:
            raise RuntimeError("Updatequelle und Programmordner sind identisch. Update wird abgebrochen, um die Installation nicht zu beschädigen.")
        self.write_update_attempt_marker(update, source_dir, target_dir)

        plan_dir = Path(os.environ.get("TEMP") or tempfile.gettempdir()) / "ODV" / "updates"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / f"odv_update_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        plan = {
            "app_name": APP_SHORT_NAME,
            "from_version": APP_VERSION,
            "to_version": str(update.get("version") or ""),
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "main_exe": "ODV.exe",
            "wait_pid": os.getpid(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        if updater.suffix.lower() == ".py":
            cmd = [sys.executable, str(updater), str(plan_path)]
        else:
            # PyInstaller-One-Dir-EXEs brauchen die _internal-Laufzeitdateien neben der EXE.
            # Deshalb wird nicht nur ODV_Updater.exe, sondern ein kleiner lauffähiger
            # Updater-Ordner in den TEMP-Bereich kopiert. Sonst erscheint unter Windows
            # "Failed to load Python DLL ... _internal\python*.dll".
            temp_updater_dir = plan_dir / "updater_runtime"
            if temp_updater_dir.exists():
                shutil.rmtree(temp_updater_dir, ignore_errors=True)
            temp_updater_dir.mkdir(parents=True, exist_ok=True)
            temp_updater = temp_updater_dir / "ODV_Updater.exe"
            shutil.copy2(updater, temp_updater)
            runtime_internal = updater.parent / "_internal"
            if runtime_internal.exists() and runtime_internal.is_dir():
                shutil.copytree(runtime_internal, temp_updater_dir / "_internal", dirs_exist_ok=True)
            else:
                raise RuntimeError("_internal-Laufzeitordner für ODV_Updater.exe wurde nicht gefunden. Bitte den vollständigen dist\\ODV-Ordner verwenden.")
            cmd = [str(temp_updater), str(plan_path)]
        # Wichtig: Den Updater erst NACH Bestätigung starten.
        # Sonst beginnt der Updater bereits zu kopieren, während die alte ODV
        # noch durch dieses Hinweisfenster läuft. Das kann Dateien sperren und
        # Update-Schleifen bzw. halb ersetzte Programmordner erzeugen.
        messagebox.showinfo(
            "ODV-Update",
            "Das Update ist vorbereitet.\n\n"
            "Nach Klick auf OK wird ODV geschlossen. Anschließend startet der Updater, "
            "ersetzt den Programmordner und startet die neue Version.",
            parent=self,
        )
        subprocess.Popen(cmd, shell=False, cwd=str(plan_dir))
        # Für ein Selbstupdate muss der alte Prozess wirklich beendet werden.
        # destroy() allein kann unter Windows noch kurz Handles offen lassen;
        # das führte im Test zu Update-Schleifen bzw. nicht ersetzten Dateien.
        try:
            self.quit()
            self.destroy()
        finally:
            os._exit(0)

    def check_app_update_on_startup(self) -> None:
        try:
            self.check_app_update(interactive=False)
        except Exception as exc:
            app_log_exception("ODV-Updateprüfung beim Start fehlgeschlagen", exc)

    def check_app_update(self, interactive: bool = False) -> None:
        """Prüft die freigegebene ODV-Version und bietet Kopie/Entpacken aus Nextcloud an."""
        try:
            update = self.get_app_update_info()
        except Exception as exc:
            if interactive:
                messagebox.showerror("ODV-Update", f"Updateinformation konnte nicht abgerufen werden:\n{exc}", parent=self)
            return
        if not update or not update.get("version"):
            if interactive:
                messagebox.showinfo("ODV-Update", "Es ist keine Updatefreigabe hinterlegt.", parent=self)
            return
        latest = str(update.get("version") or "").strip()
        if not self.is_newer_version(latest, APP_VERSION):
            if interactive:
                messagebox.showinfo("ODV-Update", f"Keine neuere Version freigegeben.\n\nLokal: {APP_VERSION}\nFreigegeben: {latest}", parent=self)
            return
        if self.has_recent_update_attempt(latest):
            hint = (
                f"Für Version {latest} wurde vor Kurzem bereits ein Updateversuch gestartet.\n\n"
                "ODV bietet dasselbe Update nicht erneut automatisch an, damit keine Endlosschleife entsteht. "
                "Bitte prüfen Sie den Updater-Log unter %TEMP%\\ODV\\updates\\odv_updater.log "
                "und starten Sie die Updateprüfung danach manuell über Hilfe → Nach ODV-Update suchen..."
            )
            if interactive:
                if not messagebox.askyesno("ODV-Update", hint + "\n\nTrotzdem erneut versuchen?", parent=self):
                    return
            else:
                app_log("warning", "Updateangebot wegen kürzlichem Updateversuch unterdrückt", latest=latest)
                return

        required = bool(update.get("required"))
        notes = str(update.get("release_notes") or update.get("notes") or "").strip()
        file_name = str(update.get("file_name") or update.get("file") or "").strip()
        msg = f"Eine neue ODV-Version ist verfügbar.\n\nLokal: {APP_VERSION}\nNeu: {latest}\nDatei: {file_name or '-'}"
        if required:
            msg += "\n\nDieses Update ist als Pflichtupdate markiert."
        if notes:
            msg += f"\n\nHinweise:\n{notes[:1200]}"
        msg += "\n\nDie neue Version wird aus dem lokalen Nextcloud-Updateordner kopiert. Danach startet der ODV-Updater, beendet diese Sitzung, ersetzt den Programmordner und startet die neue ODV-Version."
        button_text = "Update jetzt installieren?"
        if required:
            button_text = "Pflichtupdate jetzt installieren?"
        if not messagebox.askyesno("ODV-Update verfügbar", msg + "\n\n" + button_text, parent=self):
            if required:
                messagebox.showwarning("Pflichtupdate", "Dieses Update ist als Pflichtupdate markiert. Die Anwendung sollte erst nach Aktualisierung weiter genutzt werden.", parent=self)
            return
        try:
            prepared = self.stage_app_update(update)
            self.launch_comfort_updater(prepared, update)
        except Exception as exc:
            messagebox.showerror("ODV-Update", f"Update konnte nicht installiert werden:\n{exc}", parent=self)

    def open_app_update_admin_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("ODV-Updatefreigabe verwalten")
        try: self.track_window_geometry(dialog, "ODV-Updatefreigabe verwalten")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        frame = ttk.Frame(dialog, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        current = {}
        try:
            current = self.get_app_update_info()
        except Exception:
            current = {}
        version_var = tk.StringVar(value=str(current.get("version") or ""))
        file_var = tk.StringVar(value=str(current.get("file_name") or current.get("file") or ""))
        path_var = tk.StringVar(value=str(current.get("nextcloud_relative_path") or current.get("path") or "02_AUSTAUSCH/ODV_UPDATE/Windows/"))
        sha_var = tk.StringVar(value=str(current.get("sha256") or ""))
        required_var = tk.BooleanVar(value=bool(current.get("required")))
        notes_text = tk.Text(frame, width=76, height=6, wrap="word")
        fields = [
            ("Freigegebene Version:", version_var),
            ("Dateiname:", file_var),
            ("Nextcloud-Relativpfad:", path_var),
            ("SHA256-Prüfsumme:", sha_var),
        ]
        for r, (label, var) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=var, width=72).grid(row=r, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(frame, text="Pflichtupdate", variable=required_var).grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="Release-Hinweise:").grid(row=5, column=0, sticky="nw", pady=4)
        notes_text.grid(row=5, column=1, sticky="ew", pady=4)
        notes_text.insert("1.0", str(current.get("release_notes") or current.get("notes") or ""))
        hint = "Standardordner: 02_AUSTAUSCH/ODV_UPDATE/Windows. Die Datei muss dort im lokalen Nextcloud-Syncordner vorhanden sein."
        ttk.Label(frame, text=hint, wraplength=620).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 4))
        def save_release() -> None:
            payload = {
                "version": version_var.get().strip(),
                "file_name": file_var.get().strip(),
                "nextcloud_relative_path": path_var.get().strip(),
                "sha256": sha_var.get().strip(),
                "required": bool(required_var.get()),
                "release_notes": notes_text.get("1.0", "end").strip(),
            }
            if not payload["version"]:
                messagebox.showwarning("ODV-Update", "Bitte eine Version eintragen.", parent=dialog)
                return
            if not payload["file_name"] and not payload["nextcloud_relative_path"]:
                messagebox.showwarning("ODV-Update", "Bitte Dateiname oder Relativpfad eintragen.", parent=dialog)
                return
            try:
                self.api.update_app_release(self.api_token, payload)
                messagebox.showinfo("ODV-Update", "Updatefreigabe wurde gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("ODV-Update", f"Updatefreigabe konnte nicht gespeichert werden:\n{exc}", parent=dialog)
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=1, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Lokal prüfen", command=lambda: self.check_app_update(interactive=True)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save_release).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)

    def open_database_backup_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        if not messagebox.askyesno("Datenbank sichern", "Jetzt serverseitig eine Datenbanksicherung erstellen?", parent=self):
            return
        try:
            resp = self.api.create_database_backup(self.api_token)
            latest = resp.get("backup") or resp
            msg = "Datenbanksicherung wurde erstellt.\n\n"
            msg += f"Datei: {latest.get('file','?')}\n"
            msg += f"Zeitpunkt: {latest.get('created_at','?')}\n"
            msg += f"Größe: {latest.get('size_human') or latest.get('size','?')}"
            messagebox.showinfo("Datenbank sichern", msg, parent=self)
        except Exception as exc:
            messagebox.showerror("Datenbank sichern", f"Sicherung konnte nicht erstellt werden:\n{exc}", parent=self)

    def open_backup_status_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        try:
            resp = self.api.backup_status(self.api_token)
            latest = resp.get("latest") or {}
            lines = []
            if latest:
                lines.append(f"Letzte Datenbanksicherung: {latest.get('created_at','?')}")
                lines.append(f"Status: erfolgreich")
                lines.append(f"Datei: {latest.get('file','?')}")
                lines.append(f"Größe: {latest.get('size_human','?')}")
                if resp.get("warning"):
                    lines.append("\nWARNUNG: Keine aktuelle Datenbanksicherung innerhalb der letzten 48 Stunden gefunden.")
            else:
                lines.append("Keine Datenbanksicherung gefunden.")
            messagebox.showinfo("Backup-Status", "\n".join(lines), parent=self)
        except Exception as exc:
            messagebox.showerror("Backup-Status", f"Backup-Status konnte nicht geladen werden:\n{exc}", parent=self)

    def resolve_local_routes_path(self) -> Path:
        configured = str(self.config_data.get("ftp_local_routes_path", "server/routes.php") or "server/routes.php").strip()
        candidates: list[Path] = []
        raw = Path(configured)
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.append((Path.cwd() / raw).resolve())
            candidates.append((Path(__file__).resolve().parents[1] / raw).resolve())
        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return candidates[0]

    def stored_ftp_password(self) -> str:
        encrypted = str(self.config_data.get("ftp_password_dpapi", "") or "")
        if not encrypted:
            return ""
        return unprotect_text(encrypted)

    def deploy_routes_via_ftp(self) -> dict:
        host = str(self.config_data.get("ftp_host", "") or "").strip()
        port = int(str(self.config_data.get("ftp_port", "21") or "21").strip())
        user = str(self.config_data.get("ftp_user", "") or "").strip()
        remote_path = str(self.config_data.get("ftp_remote_routes_path", "") or "").strip()
        password = self.stored_ftp_password()
        local_path = self.resolve_local_routes_path()
        if not host or not user or not remote_path:
            raise RuntimeError("FTP-Server, Benutzer oder Zielpfad fehlen in den Admin-Einstellungen.")
        if not password:
            raise RuntimeError("FTP-Passwort ist noch nicht gespeichert. Bitte einmal in den Admin-Einstellungen erfassen.")
        if not local_path.exists():
            raise RuntimeError(f"Lokale routes.php nicht gefunden: {local_path}")
        remote_dir = posixpath.dirname(remote_path)
        remote_name = posixpath.basename(remote_path)
        if not remote_dir or not remote_name:
            raise RuntimeError("FTP-Zielpfad ist ungültig.")
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        stem, ext = posixpath.splitext(remote_name)
        backup_name = f"{stem}_backup_{APP_VERSION}_{stamp}{ext or '.php'}"
        with ftplib.FTP() as ftp:
            ftp.connect(host, port, timeout=30)
            ftp.login(user, password)
            ftp.cwd(remote_dir)
            existing = ftp.nlst()
            backup_created = False
            if remote_name in existing:
                ftp.rename(remote_name, backup_name)
                backup_created = True
            with local_path.open("rb") as fh:
                ftp.storbinary(f"STOR {remote_name}", fh)
            size = ftp.size(remote_name)
        return {
            "host": host,
            "remote_dir": remote_dir,
            "remote_name": remote_name,
            "backup_name": backup_name if backup_created else "",
            "local_path": str(local_path),
            "size": size,
        }

    def open_routes_deploy_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Server-routes.php sichern/hochladen")
        try: self.track_window_geometry(dialog, "Server-routes.php sichern/hochladen")
        except Exception: pass
        dialog.geometry("780x430")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        local_path = self.resolve_local_routes_path()
        remote_path = str(self.config_data.get("ftp_remote_routes_path", "") or "")
        server = str(self.config_data.get("ftp_host", "") or "")
        user = str(self.config_data.get("ftp_user", "") or "")
        port = str(self.config_data.get("ftp_port", "21") or "21")
        password_saved = bool(str(self.config_data.get("ftp_password_dpapi", "") or "").strip())

        text = (
            "ODV sichert die vorhandene routes.php auf dem Webserver und lädt danach die lokale Datei hoch.\n\n"
            f"Lokal: {local_path}\n"
            f"Server: {server}:{port}\n"
            f"Benutzer: {user}\n"
            f"Ziel: {remote_path}\n"
            f"Passwort gespeichert: {'ja' if password_saved else 'nein'}"
        )
        ttk.Label(dialog, text="Server-routes.php sichern/hochladen", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        ttk.Label(dialog, text=text, wraplength=740).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        result_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=result_var, wraplength=740).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

        def run_deploy() -> None:
            if not messagebox.askyesno(
                "routes.php hochladen",
                "Jetzt die Server-routes.php sichern und die lokale server/routes.php hochladen?",
                parent=dialog,
            ):
                return
            result_var.set("Upload läuft ...")
            for child in buttons.winfo_children():
                child.configure(state="disabled")

            def worker() -> None:
                try:
                    info = self.deploy_routes_via_ftp()
                    lines = [
                        "Upload abgeschlossen.",
                        f"Lokale Datei: {info.get('local_path')}",
                        f"Serverziel: {info.get('remote_dir')}/{info.get('remote_name')}",
                        f"Größe: {info.get('size')} Byte",
                    ]
                    if info.get("backup_name"):
                        lines.append(f"Backup auf Server: {info.get('backup_name')}")
                    else:
                        lines.append("Kein Server-Backup erstellt, weil keine vorhandene routes.php gefunden wurde.")
                    self.after(0, lambda: result_var.set("\n".join(lines)))
                    self.after(0, lambda: messagebox.showinfo("routes.php hochladen", "routes.php wurde hochgeladen.", parent=dialog))
                except Exception as exc:
                    self.after(0, lambda error=str(exc): result_var.set(f"Upload fehlgeschlagen: {error}"))
                    self.after(0, lambda error=str(exc): messagebox.showerror("routes.php hochladen", f"Upload fehlgeschlagen:\n{error}", parent=dialog))
                finally:
                    self.after(0, lambda: [child.configure(state="normal") for child in buttons.winfo_children()])

            threading.Thread(target=worker, daemon=True).start()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, sticky="e", padx=12, pady=(10, 12))
        ttk.Button(buttons, text="Sichern und hochladen", command=run_deploy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)

    def open_database_migrations_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Datenbankmigrationen")
        try: self.track_window_geometry(dialog, "Datenbankmigrationen")
        except Exception: pass
        dialog.geometry("820x520")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        info_var = tk.StringVar(value="Status wird geladen ...")
        ttk.Label(dialog, text="Datenbankmigrationen", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ttk.Label(dialog, textvariable=info_var, wraplength=780).grid(row=1, column=0, sticky="new", padx=12, pady=(0, 8))
        columns = ("key", "from", "to", "status", "description")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=10)
        tree.heading("key", text="Migration")
        tree.heading("from", text="Von")
        tree.heading("to", text="Nach")
        tree.heading("status", text="Status")
        tree.heading("description", text="Beschreibung")
        tree.column("key", width=210)
        tree.column("from", width=70, anchor="center")
        tree.column("to", width=70, anchor="center")
        tree.column("status", width=100, anchor="center")
        tree.column("description", width=320)
        tree.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        dialog.rowconfigure(2, weight=1)

        last_status: dict = {}

        def render_status(resp: dict) -> None:
            last_status.clear()
            last_status.update(resp)
            for iid in tree.get_children():
                tree.delete(iid)
            for migration in resp.get("migrations", []) or []:
                status = "offen" if migration.get("pending") else "erledigt"
                tree.insert("", "end", values=(
                    migration.get("key", ""),
                    migration.get("from_version", ""),
                    migration.get("to_version", ""),
                    status,
                    migration.get("description", ""),
                ))
            backup = resp.get("latest_backup") or resp.get("backup") or {}
            backup_text = "keine letzte Sicherung"
            if backup:
                backup_text = f"letzte Sicherung: {backup.get('created_at','?')} ({backup.get('file','?')})"
            info_var.set(f"API-Version: {resp.get('api_version', '?')} | offene Migrationen: {resp.get('pending_count', 0)} | {backup_text}")

        def refresh() -> None:
            try:
                render_status(self.api.schema_migrations(self.api_token))
            except Exception as exc:
                info_var.set(f"Status konnte nicht geladen werden: {exc}")

        def apply() -> None:
            pending = int(last_status.get("pending_count") or 0)
            if pending <= 0:
                messagebox.showinfo("Datenbankmigrationen", "Keine offenen Migrationen vorhanden.", parent=dialog)
                return
            warning = (
                "Migrationen jetzt ausführen?\n\n"
                "Die API erstellt vorher automatisch eine vollständige Datenbanksicherung. "
                "Bei künftigen Tabellenänderungen werden betroffene Tabellen zusätzlich mit der vorherigen Versionsnummer kopiert."
            )
            if not messagebox.askyesno("Datenbankmigrationen", warning, parent=dialog):
                return
            try:
                resp = self.api.apply_schema_migrations(self.api_token)
                applied = resp.get("applied", []) or []
                render_status(resp)
                messagebox.showinfo("Datenbankmigrationen", "Migration abgeschlossen.\n\nAusgeführt: " + (", ".join(applied) if applied else "keine"), parent=dialog)
            except Exception as exc:
                messagebox.showerror("Datenbankmigrationen", f"Migration fehlgeschlagen:\n{exc}", parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, sticky="e", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Status aktualisieren", command=refresh).pack(side="left", padx=4)
        ttk.Button(buttons, text="Offene Migrationen ausführen", command=apply).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        refresh()

    def open_database_restore_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Backup zurücksichern")
        try: self.track_window_geometry(dialog, "Backup zurücksichern")
        except Exception: pass
        dialog.geometry("820x520")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        warning = (
            "Diese Funktion spielt ein serverseitiges Datenbankbackup zurück.\n\n"
            "Vor der Rücksicherung erstellt die API automatisch ein frisches Backup des aktuellen Stands. "
            "Danach ersetzt das ausgewählte Backup die aktuelle Datenbankstruktur und Daten."
        )
        ttk.Label(dialog, text="Backup zurücksichern", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ttk.Label(dialog, text=warning, wraplength=780, foreground="#8a0000").grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        columns = ("file", "created_at", "size")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=10)
        tree.heading("file", text="Backup-Datei")
        tree.heading("created_at", text="Erstellt")
        tree.heading("size", text="Größe")
        tree.column("file", width=430)
        tree.column("created_at", width=170, anchor="center")
        tree.column("size", width=100, anchor="e")
        tree.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))

        ttk.Label(dialog, text="Zum Bestätigen exakt eingeben: BACKUP ZURUECKSICHERN").grid(row=3, column=0, sticky="w", padx=12, pady=(4, 2))
        confirm_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=confirm_var).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        result_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=result_var, wraplength=780).grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))

        def load_backups() -> None:
            try:
                resp = self.api.list_database_backups(self.api_token)
                for iid in tree.get_children():
                    tree.delete(iid)
                for item in resp.get("backups", []) or []:
                    file = str(item.get("file", ""))
                    if file:
                        tree.insert("", "end", iid=file, values=(file, item.get("created_at", ""), item.get("size_human", "")))
                result_var.set(f"{len(tree.get_children())} Backup(s) gefunden.")
            except Exception as exc:
                result_var.set(f"Backups konnten nicht geladen werden: {exc}")

        def selected_backup_file() -> str:
            sel = tree.selection()
            return str(sel[0]) if sel else ""

        def run_restore() -> None:
            file = selected_backup_file()
            if not file:
                messagebox.showwarning("Backup zurücksichern", "Bitte ein Backup auswählen.", parent=dialog)
                return
            if confirm_var.get().strip() != "BACKUP ZURUECKSICHERN":
                messagebox.showwarning("Sicherheitsabfrage", "Der Bestätigungstext stimmt nicht.", parent=dialog)
                return
            if not messagebox.askyesno("Backup endgültig zurücksichern", f"Backup jetzt zurücksichern?\n\n{file}", parent=dialog):
                return
            try:
                resp = self.api.restore_database_backup(self.api_token, file, confirm_var.get().strip())
                before = resp.get("before_backup") or {}
                restore = resp.get("restore") or {}
                msg = [
                    "Backup wurde zurückgesichert.",
                    f"Zurückgesichert: {restore.get('file', file)}",
                    f"Vorheriger Stand gesichert als: {before.get('file', '?')}",
                    f"SQL-Anweisungen: {restore.get('statements_executed', '?')}",
                ]
                result_var.set("\n".join(msg))
                messagebox.showinfo("Backup zurücksichern", "\n".join(msg), parent=dialog)
            except Exception as exc:
                messagebox.showerror("Backup zurücksichern", f"Rücksicherung fehlgeschlagen:\n{exc}", parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=6, column=0, sticky="e", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Aktualisieren", command=load_backups).pack(side="left", padx=4)
        ttk.Button(buttons, text="Backup zurücksichern", command=run_restore).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        load_backups()

    def open_maintenance_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Wartungsmodus / Datenbanksperre")
        try: self.track_window_geometry(dialog, "Wartungsmodus / Datenbanksperre")
        except Exception: pass
        dialog.geometry("620x360")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        frm = ttk.Frame(dialog, padding=14)
        frm.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frm, text="Wartungsmodus / Datenbanksperre", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        info_var = tk.StringVar(value="Status wird geladen …")
        ttk.Label(frm, textvariable=info_var, wraplength=570).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        ttk.Label(frm, text="Sperre aktivieren in Minuten:").grid(row=2, column=0, sticky="w", pady=6)
        minutes_var = tk.StringVar(value="5")
        ttk.Entry(frm, textvariable=minutes_var, width=8).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(frm, text="Hinweistext:").grid(row=3, column=0, sticky="nw", pady=6)
        msg = tk.Text(frm, width=54, height=4, wrap="word")
        msg.grid(row=3, column=1, sticky="ew", pady=6)
        msg.insert("1.0", "Die ODV-Datenbank wird für Wartungsarbeiten gesperrt. Bitte speichern Sie Ihre Arbeit.")
        def refresh():
            try:
                st = self.api.maintenance_status(self.api_token)
                m = st.get("maintenance") or {}
                if m.get("active"):
                    info_var.set(f"Aktuell aktiv seit {m.get('starts_at','?')}. Superadmin bleibt zugriffsberechtigt.")
                elif m.get("scheduled"):
                    info_var.set(f"Geplant ab {m.get('starts_at','?')}. Nicht-Superadmins werden dann gesperrt.")
                else:
                    info_var.set("Wartungsmodus ist aktuell nicht aktiv/geplant.")
            except Exception as exc:
                info_var.set(f"Status konnte nicht geladen werden: {exc}")
        def activate():
            try:
                minutes = int(minutes_var.get().strip() or "0")
                if minutes < 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Wartungsmodus", "Bitte eine gültige Minutenzahl eingeben.", parent=dialog)
                return
            prompt = "Wartungsmodus sofort aktivieren?" if minutes == 0 else f"Wartungsmodus in {minutes} Minute(n) aktivieren?"
            if not messagebox.askyesno("Wartungsmodus", prompt, parent=dialog):
                return
            try:
                resp = self.api.set_maintenance(self.api_token, minutes, msg.get("1.0", "end").strip())
                refresh()
                m = resp.get("maintenance") or {}
                starts = m.get("starts_at") or ("sofort" if minutes == 0 else f"in {minutes} Minute(n)")
                warn = (
                    "Wartungsmodus wurde gesetzt.\n\n"
                    f"Die ODV-Datenbank wird {('sofort' if minutes == 0 else 'in ' + str(minutes) + ' Minute(n)')} für Wartungsarbeiten gesperrt.\n"
                    f"Aktiv ab: {starts}\n\n"
                    "Bitte offene Eingaben speichern.\n"
                    "Superadmins bleiben zugriffsberechtigt. Admins und Ortschronisten werden nach Ablauf gesperrt."
                )
                messagebox.showwarning("Wartungsmodus geplant", warn, parent=dialog)
            except Exception as exc:
                messagebox.showerror("Wartungsmodus", f"Wartungsmodus konnte nicht gesetzt werden:\n{exc}", parent=dialog)
        def deactivate():
            if not messagebox.askyesno("Wartungsmodus", "Wartungsmodus beenden?", parent=dialog):
                return
            try:
                self.api.clear_maintenance(self.api_token)
                refresh()
                messagebox.showinfo("Wartungsmodus", "Wartungsmodus wurde beendet.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Wartungsmodus", f"Wartungsmodus konnte nicht beendet werden:\n{exc}", parent=dialog)
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="Status aktualisieren", command=refresh).pack(side="left", padx=4)
        ttk.Button(btns, text="Aktivieren", command=activate).pack(side="left", padx=4)
        ttk.Button(btns, text="Beenden", command=deactivate).pack(side="left", padx=4)
        ttk.Button(btns, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        refresh()

    def open_database_reset_dialog(self) -> None:
        """Setzt Test-/Bewegungsdaten der zentralen MySQL-Datenbank zurück."""
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Datenbank zurücksetzen")
        try: self.track_window_geometry(dialog, "Datenbank zurücksetzen")
        except Exception: pass
        dialog.geometry("760x460")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        warning = (
            "Diese Funktion löscht Bewegungs-/Testdaten aus der zentralen Datenbank.\n\n"
            "Gelöscht werden: Dokumente, Metadaten, Personenmarkierungen, Dokumenthistorie, Punkte, Sonderpunkte "
            "und optional Mail-Versandhistorie.\n\n"
            "NICHT gelöscht werden: Benutzer, Rollen, Rechte, Ortsordner, Punkteregeln, Verteiler und Systemeinstellungen.\n"
            "Nextcloud-Dateien werden nicht gelöscht. Vorhandene Dateien müssen danach bei Bedarf neu eingelesen werden.\n\n"
            "Bitte vorher ein MySQL-Backup erstellen."
        )
        ttk.Label(dialog, text=warning, wraplength=720, foreground="#8a0000").grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        include_mail_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Mail-Versandhistorie ebenfalls löschen", variable=include_mail_var).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 8))
        ttk.Label(dialog, text="Zum Bestätigen exakt eingeben: DATENBANK ZURUECKSETZEN").grid(row=2, column=0, sticky="w", padx=12, pady=(8, 4))
        confirm_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=confirm_var).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        result_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=result_var, wraplength=720).grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 8))
        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, sticky="e", padx=12, pady=12)
        def run_reset() -> None:
            if confirm_var.get().strip() != "DATENBANK ZURUECKSETZEN":
                messagebox.showwarning("Sicherheitsabfrage", "Der Bestätigungstext stimmt nicht.", parent=dialog)
                return
            if not messagebox.askyesno("Endgültig zurücksetzen", "Datenbank-Bewegungsdaten jetzt endgültig zurücksetzen?", parent=dialog):
                return
            try:
                resp = self.api.reset_database(self.api_token, confirm_var.get().strip(), include_mail_var.get())
                deleted = resp.get("deleted", {})
                lines = ["Datenbank wurde zurückgesetzt."]
                if isinstance(deleted, dict):
                    for key, val in deleted.items():
                        lines.append(f"{key}: {val}")
                result_var.set("\n".join(lines))
                self.refresh_dashboard()
                self.refresh_admin_uploads(show_message=False)
                messagebox.showinfo("Datenbank zurücksetzen", "Zurücksetzen abgeschlossen. Nextcloud-Dateien wurden nicht gelöscht.", parent=dialog)
            except ApiError as exc:
                messagebox.showerror("Datenbank zurücksetzen", f"Zurücksetzen fehlgeschlagen:\n{exc}", parent=dialog)
        ttk.Button(buttons, text="Datenbank zurücksetzen", command=run_reset).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)

    def open_mail_group_management_dialog(self) -> None:
        if not self.api_token:
            messagebox.showerror("Verteiler", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        users = self.load_email_users()
        groups = self.load_mail_groups()

        dialog = tk.Toplevel(self)
        dialog.title("Verteiler verwalten")
        try: self.track_window_geometry(dialog, "Verteiler verwalten")
        except Exception: pass
        dialog.geometry("1060x720")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=0)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(dialog, text="Verteiler", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.rowconfigure(0, weight=1)
        group_list = tk.Listbox(left, width=32, exportselection=False)
        group_list.grid(row=0, column=0, sticky="nsew")
        group_scroll = ttk.Scrollbar(left, orient="vertical", command=group_list.yview)
        group_list.configure(yscrollcommand=group_scroll.set)
        group_scroll.grid(row=0, column=1, sticky="ns")

        right = ttk.LabelFrame(dialog, text="Verteiler bearbeiten", padding=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)
        right.rowconfigure(4, weight=0)

        name_var = tk.StringVar()
        desc_var = tk.StringVar()
        active_var = tk.BooleanVar(value=True)
        selected_group = {"id": None}
        member_vars: dict[int, tk.BooleanVar] = {}

        ttk.Label(right, text="Name:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=name_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(right, text="Beschreibung:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=desc_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(right, text="Verteiler aktiv", variable=active_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        members_frame = ttk.LabelFrame(right, text="Mitglieder aus Benutzern", padding=6)
        members_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 4))
        members_frame.columnconfigure(0, weight=1)
        members_canvas = tk.Canvas(members_frame, highlightthickness=0)
        members_scroll = ttk.Scrollbar(members_frame, orient="vertical", command=members_canvas.yview)
        members_inner = ttk.Frame(members_canvas)
        members_inner.bind("<Configure>", lambda e: members_canvas.configure(scrollregion=members_canvas.bbox("all")))
        members_canvas.create_window((0, 0), window=members_inner, anchor="nw")
        members_canvas.configure(yscrollcommand=members_scroll.set)
        members_canvas.grid(row=0, column=0, sticky="nsew")
        members_scroll.grid(row=0, column=1, sticky="ns")
        members_frame.rowconfigure(0, weight=1)

        for idx, user in enumerate(users):
            uid = int(user.get("id", 0) or 0)
            if uid <= 0:
                continue
            var = tk.BooleanVar(value=False)
            member_vars[uid] = var
            label = f"{user.get('display_name','')} <{user.get('email','')}> ({user.get('place','') or user.get('role','')})"
            ttk.Checkbutton(members_inner, text=label, variable=var).grid(row=idx, column=0, sticky="w", pady=1)

        external_frame = ttk.LabelFrame(right, text="Externe Empfänger (Vorname; Name; E-Mail)", padding=6)
        external_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        external_frame.columnconfigure(0, weight=1)
        external_text = tk.Text(external_frame, height=5, wrap="none")
        external_text.grid(row=0, column=0, sticky="ew")
        external_scroll = ttk.Scrollbar(external_frame, orient="vertical", command=external_text.yview)
        external_text.configure(yscrollcommand=external_scroll.set)
        external_scroll.grid(row=0, column=1, sticky="ns")
        ttk.Label(external_frame, text="Eine Zeile je Kontakt, z. B.: Max; Mustermann; max@example.de", foreground="#555555").grid(row=1, column=0, sticky="w", pady=(3, 0))

        def parse_external_members() -> list[dict]:
            result = []
            for line in external_text.get("1.0", "end").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(";")]
                if len(parts) >= 3:
                    first, last, email = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    first, last, email = "", parts[0], parts[1]
                else:
                    first, last, email = "", "", parts[0]
                if email:
                    result.append({"first_name": first, "last_name": last, "email": email, "is_active": True})
            return result

        def set_external_members(members: list[dict]) -> None:
            external_text.delete("1.0", "end")
            lines = []
            for m in members or []:
                lines.append(f"{m.get('first_name','')}; {m.get('last_name','')}; {m.get('email','')}")
            external_text.insert("1.0", "\n".join(lines))

        def refresh_group_list(select_id: int | None = None):
            group_list.delete(0, "end")
            for g in groups:
                status = "" if int(g.get("is_active", 1) or 0) == 1 else " (inaktiv)"
                group_list.insert("end", f"{g.get('name','')}{status}")
            if select_id is not None:
                for i, g in enumerate(groups):
                    if int(g.get("id", 0) or 0) == int(select_id):
                        group_list.selection_set(i)
                        group_list.see(i)
                        load_selected()
                        break

        def clear_form():
            selected_group["id"] = None
            name_var.set("")
            desc_var.set("")
            active_var.set(True)
            for var in member_vars.values():
                var.set(False)
            set_external_members([])
            try:
                group_list.selection_clear(0, "end")
            except tk.TclError:
                pass

        def load_selected(_event=None):
            sel = group_list.curselection()
            if not sel:
                return
            g = groups[int(sel[0])]
            selected_group["id"] = int(g.get("id", 0) or 0) or None
            name_var.set(g.get("name", ""))
            desc_var.set(g.get("description", "") or "")
            active_var.set(int(g.get("is_active", 1) or 0) == 1)
            members = {int(m.get("user_id", 0) or 0) for m in g.get("members", [])}
            for uid, var in member_vars.items():
                var.set(uid in members)
            set_external_members(list(g.get("external_members", []) or []))

        def save_groups():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Verteiler", "Bitte einen Verteilernamen erfassen.", parent=dialog)
                return
            member_ids = [uid for uid, var in member_vars.items() if var.get()]
            gid = selected_group.get("id")
            if gid is None:
                gid = 0
            payload_group = {
                "id": gid,
                "name": name,
                "description": desc_var.get().strip(),
                "is_active": bool(active_var.get()),
                "member_user_ids": member_ids,
                "external_members": parse_external_members(),
            }
            # API erwartet vollständige Liste; bestehenden Verteiler ersetzen/ergänzen.
            out = []
            replaced = False
            for g in groups:
                if gid and int(g.get("id", 0) or 0) == int(gid):
                    out.append(payload_group)
                    replaced = True
                else:
                    out.append({
                        "id": int(g.get("id", 0) or 0),
                        "name": g.get("name", ""),
                        "description": g.get("description", "") or "",
                        "is_active": bool(int(g.get("is_active", 1) or 0)),
                        "member_user_ids": [int(m.get("user_id", 0) or 0) for m in g.get("members", [])],
                        "external_members": list(g.get("external_members", []) or []),
                    })
            if not replaced:
                out.append(payload_group)
            try:
                response = self.api.update_mail_groups(self.api_token, out)
                groups[:] = list(response.get("groups", []))
                messagebox.showinfo("Verteiler", "Verteiler wurden gespeichert.", parent=dialog)
                refresh_group_list()
                clear_form()
            except Exception as exc:
                messagebox.showerror("Verteiler", f"Verteiler konnten nicht gespeichert werden:\n{exc}", parent=dialog)

        group_list.bind("<<ListboxSelect>>", load_selected)
        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Neu", command=clear_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Verteiler speichern", command=save_groups).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        refresh_group_list()

    def fallback_nextcloud_folder_link_for_local_path(self, file_path: str) -> str:
        """Fallback: Link in die Nextcloud-Dateiansicht des Ordners erzeugen."""
        raw = (file_path or "").strip()
        if not raw:
            return ""
        base_url = (self.config_data.get("nextcloud_web_files_url") or "").strip().rstrip("/")
        if not base_url:
            return raw
        try:
            nc_base = Path(self.base_folder_var.get().strip()).resolve()
            path = Path(raw).resolve()
            rel = path.relative_to(nc_base)
            folder_rel = rel.parent.as_posix()
            if folder_rel == ".":
                folder_rel = ""
            dir_part = "/" + folder_rel if folder_rel else "/"
            return base_url + "?dir=" + urllib.parse.quote(dir_part, safe="/")
        except Exception:
            return raw

    def nextcloud_web_link_for_local_path(self, file_path: str) -> str:
        """Erzeugt bevorzugt einen öffentlichen Nextcloud-Downloadlink über die API.

        Die App übergibt lokalen Dateipfad und lokales Nextcloud-Stammverzeichnis.
        Der Server rechnet daraus den Remote-Pfad und erstellt mit der Nextcloud-API
        einen Freigabelink. Falls das fehlschlägt, wird als Fallback ein Link in die
        Nextcloud-Dateiansicht des Ordners erzeugt.
        """
        raw = (file_path or "").strip()
        if not raw:
            return ""
        if self.api.configured() and self.api_token:
            try:
                base = self.base_folder_var.get().strip()
                response = self.api.create_nextcloud_share(self.api_token, raw, base)
                return (response.get("download_url") or response.get("share_url") or "").strip()
            except Exception as exc:
                app_log_exception("Nextcloud-Freigabelink konnte nicht erstellt werden; Fallback wird verwendet", exc)
                messagebox.showwarning(
                    "Nextcloud-Link",
                    "Der öffentliche Nextcloud-Downloadlink konnte nicht automatisch erzeugt werden.\n"
                    "Es wird stattdessen ein Link in die Nextcloud-Dateiansicht des Ordners verwendet.\n\n"
                    f"Fehler: {exc}"
                )
        return self.fallback_nextcloud_folder_link_for_local_path(raw)

    def build_mail_attachment_payload(self, file_path: str) -> dict | None:
        raw = (file_path or "").strip()
        if not raw:
            return None
        path = Path(raw)
        if not path.exists() or not path.is_file():
            raise ValueError("Die ausgewählte Anlage wurde nicht gefunden.")
        size = path.stat().st_size
        max_size = 8 * 1024 * 1024
        if size > max_size:
            raise ValueError("Die Anlage ist größer als 8 MB. Bitte besser als Nextcloud-Link versenden.")
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"filename": path.name, "mime_type": mime, "content_base64": data, "size": size}

    def open_information_mail_dialog(self) -> None:
        """Rundmail erstellen und optional direkt über die Server-API versenden."""
        if not self.is_current_admin():
            messagebox.showerror("Rundmail", "Nur Admins und Superadmins können Rundmails erstellen.")
            return
        users = self.load_email_users()
        groups = [g for g in self.load_mail_groups() if int(g.get("is_active", 1) or 0) == 1]

        dialog = tk.Toplevel(self)
        dialog.title("Rundmail erstellen")
        try: self.track_window_geometry(dialog, "Rundmail erstellen")
        except Exception: pass
        dialog.geometry("1120x820")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=0)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(7, weight=1)

        ttk.Label(dialog, text="Empfänger aus Benutzern:").grid(row=0, column=0, sticky="nw", padx=10, pady=8)
        rec_frame = ttk.Frame(dialog)
        rec_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=8)
        rec_frame.columnconfigure(0, weight=1)
        user_list = tk.Listbox(rec_frame, selectmode="extended", height=8, exportselection=False)
        user_list.grid(row=0, column=0, sticky="nsew")
        rec_scroll = ttk.Scrollbar(rec_frame, orient="vertical", command=user_list.yview)
        user_list.configure(yscrollcommand=rec_scroll.set)
        rec_scroll.grid(row=0, column=1, sticky="ns")
        for user in users:
            user_list.insert("end", f"{user.get('display_name','')} <{user.get('email','')}> ({user.get('place','') or user.get('role','')})")

        ttk.Label(dialog, text="Verteiler:").grid(row=1, column=0, sticky="nw", padx=10, pady=8)
        group_frame = ttk.Frame(dialog)
        group_frame.grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        group_vars: list[tuple[tk.BooleanVar, dict]] = []
        if groups:
            for idx, group in enumerate(groups):
                var = tk.BooleanVar(value=False)
                group_vars.append((var, group))
                text = f"{group.get('name','')} ({len(group.get('members', []))} Empfänger)"
                ttk.Checkbutton(group_frame, text=text, variable=var).grid(row=idx // 3, column=idx % 3, sticky="w", padx=(0, 18), pady=2)
        else:
            ttk.Label(group_frame, text="Keine Verteiler vorhanden. Über Informationen > Verteiler verwalten anlegen.").grid(row=0, column=0, sticky="w")

        ttk.Label(dialog, text="Weitere Empfänger:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        manual_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=manual_var).grid(row=2, column=1, sticky="ew", padx=10, pady=8)
        ttk.Label(dialog, text="E-Mail-Adressen mit Semikolon trennen. Direkter Versand erfolgt einzeln je Empfänger.", foreground="#555").grid(row=3, column=1, sticky="w", padx=10)

        ttk.Label(dialog, text="Versandart:").grid(row=4, column=0, sticky="w", padx=10, pady=8)
        mode_frame = ttk.Frame(dialog)
        mode_frame.grid(row=4, column=1, sticky="w", padx=10, pady=8)
        send_mode_var = tk.StringVar(value="none")
        ttk.Radiobutton(mode_frame, text="Keine Anlage", variable=send_mode_var, value="none").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(mode_frame, text="Nextcloud-Downloadlink versenden", variable=send_mode_var, value="link").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(mode_frame, text="Dokument anhängen", variable=send_mode_var, value="attachment").pack(side="left")

        fields = ttk.Frame(dialog)
        fields.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        fields.columnconfigure(1, weight=1)
        ttk.Label(fields, text="Betreff:").grid(row=0, column=0, sticky="w", pady=4)
        subject_var = tk.StringVar(value="Information der Ortschronisten")
        ttk.Entry(fields, textvariable=subject_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(fields, text="Dokumente / Anhänge:").grid(row=1, column=0, sticky="nw", pady=4)
        doc_path_var = tk.StringVar()
        link_var = tk.StringVar()
        selected_docs: list[str] = []
        generated_links: dict[str, str] = {}
        doc_frame = ttk.Frame(fields)
        doc_frame.grid(row=1, column=1, sticky="ew", pady=4)
        doc_frame.columnconfigure(1, weight=1)
        ttk.Button(doc_frame, text="+", width=3, command=lambda: add_doc()).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(doc_frame, textvariable=doc_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(doc_frame, text="Entfernen", command=lambda: remove_selected_doc()).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(doc_frame, text="Leeren", command=lambda: clear_docs()).grid(row=0, column=3, padx=(6, 0))
        doc_list = tk.Listbox(doc_frame, height=4, exportselection=False)
        doc_list.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Label(doc_frame, text="Mit + können Dokumente nacheinander hinzugefügt werden. Bei Downloadlink werden alle ausgewählten Dateien als Linkliste in die Mail geschrieben.", foreground="#555").grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(fields, text="Dokumentenliste:").grid(row=2, column=0, sticky="nw", pady=4)
        link_frame = ttk.Frame(fields)
        link_frame.grid(row=2, column=1, sticky="ew", pady=4)
        link_frame.columnconfigure(0, weight=1)
        link_text, link_text_frame = self.make_scrolled_text(link_frame, height=5, wrap="word")
        link_text_frame.grid(row=0, column=0, sticky="ew")
        ttk.Button(link_frame, text="Downloadlinks erzeugen", command=lambda: refresh_document_block(force_links=True)).grid(row=0, column=1, padx=(6, 0), sticky="n")

        def refresh_doc_display():
            doc_list.delete(0, "end")
            for path in selected_docs:
                doc_list.insert("end", Path(path).name)
            if not selected_docs:
                doc_path_var.set("")
            elif len(selected_docs) == 1:
                doc_path_var.set(selected_docs[0])
            else:
                doc_path_var.set(f"{len(selected_docs)} Dateien ausgewählt")
            refresh_document_block(force_links=False)

        def clear_docs():
            selected_docs.clear()
            generated_links.clear()
            doc_path_var.set("")
            link_var.set("")
            doc_list.delete(0, "end")
            link_text.delete("1.0", "end")

        def add_doc():
            fns = filedialog.askopenfilenames(title="Dokument(e) hinzufügen", parent=dialog)
            if fns:
                existing = {str(Path(x).resolve()).lower(): x for x in selected_docs}
                for fn in fns:
                    key = str(Path(fn).resolve()).lower()
                    if key not in existing:
                        selected_docs.append(str(fn))
                        existing[key] = str(fn)
                refresh_doc_display()

        def remove_selected_doc():
            idxs = list(doc_list.curselection())
            if not idxs:
                return
            for idx in sorted(idxs, reverse=True):
                if 0 <= idx < len(selected_docs):
                    generated_links.pop(selected_docs[idx], None)
                    del selected_docs[idx]
            refresh_doc_display()

        def build_documents_block(force_links: bool = False) -> str:
            if not selected_docs:
                return ""
            parts = []
            for path in selected_docs:
                name = Path(path).name
                link = generated_links.get(path, "")
                if force_links or send_mode_var.get() == "link":
                    if not link:
                        link = self.nextcloud_web_link_for_local_path(path)
                        generated_links[path] = link
                parts.append(f"Datei: {name}")
                if link:
                    parts.append(f"Downloadlink: {link}")
                parts.append("")
            return "\n".join(parts).strip()

        def refresh_document_block(force_links: bool = False):
            block = build_documents_block(force_links=force_links)
            link_var.set(block)
            link_text.delete("1.0", "end")
            link_text.insert("1.0", block)

        ttk.Label(dialog, text="Text:").grid(row=6, column=0, sticky="nw", padx=10, pady=4)
        body, body_frame = self.make_scrolled_text(dialog, height=18, wrap="word")
        body_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", padx=10, pady=4)
        body.insert("1.0", "Liebe Ortschronistinnen und Ortschronisten,\n\n"
                         "es liegt eine neue Information / Einladung vor.\n\n"
                         "DOKUMENTE:\n{dokumente}\n\n"
                         "Viele Grüße\n"
                         f"{self.display_name_var.get().strip() or 'Ortschronisten'}")

        def collect_recipients() -> list[str]:
            emails: list[str] = []
            for idx in user_list.curselection():
                email = str(users[int(idx)].get("email", "") or "").strip()
                if email:
                    emails.append(email)
            for var, group in group_vars:
                if not var.get():
                    continue
                for member in list(group.get("members", []) or []) + list(group.get("external_members", []) or []):
                    email = str(member.get("email", "") or "").strip()
                    if email:
                        emails.append(email)
            for part in manual_var.get().replace(",", ";").split(";"):
                email = part.strip()
                if email:
                    emails.append(email)
            seen = set()
            out = []
            for email in emails:
                key = email.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(email)
            return out

        def render_body() -> str:
            if selected_docs:
                doc_name = ", ".join(Path(x).name for x in selected_docs)
            else:
                doc_name = Path(doc_path_var.get()).name if doc_path_var.get().strip() else ""
            document_block = link_var.get().strip()
            if send_mode_var.get() == "none":
                document_block = ""
                doc_name = ""
            elif selected_docs and send_mode_var.get() == "link" and not document_block:
                document_block = build_documents_block(force_links=True)
            elif selected_docs and send_mode_var.get() == "attachment" and not document_block:
                document_block = "\n".join(f"Datei: {Path(x).name}" for x in selected_docs)
            return (body.get("1.0", "end")
                    .replace("{dokumente}", document_block)
                    .replace("{link}", document_block)
                    .replace("{datei}", doc_name)
                    .strip())

        def copy_mail_text():
            recipients = collect_recipients()
            text = f"Betreff: {subject_var.get().strip()}\nEmpfänger/BCC: {'; '.join(recipients)}\nVersandart: {send_mode_var.get()}\n\n{render_body()}"
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Kopiert", f"Der E-Mail-Text wurde in die Zwischenablage kopiert.\nEmpfänger: {len(recipients)}", parent=dialog)

        def open_mail_client():
            recipients = collect_recipients()
            if not recipients:
                messagebox.showwarning("Rundmail", "Bitte mindestens einen Empfänger auswählen oder manuell eintragen.", parent=dialog)
                return
            if send_mode_var.get() == "attachment":
                messagebox.showinfo("Hinweis", "Anhänge können über mailto nicht zuverlässig automatisch übernommen werden.\nBitte für Anhänge den direkten Versand nutzen oder Dateien im Mailprogramm manuell anhängen.", parent=dialog)
            subject = urllib.parse.quote(subject_var.get().strip())
            mail_body = urllib.parse.quote(render_body())
            bcc = urllib.parse.quote(";".join(recipients))
            url = f"mailto:?bcc={bcc}&subject={subject}&body={mail_body}"
            try:
                webbrowser.open(url)
                app_log("info", "Rundmail im Mailprogramm geöffnet", recipients=len(recipients))
            except Exception as exc:
                app_log_exception("Mailprogramm konnte nicht geöffnet werden", exc)
                messagebox.showerror("Rundmail", f"Mailprogramm konnte nicht geöffnet werden:\n{exc}", parent=dialog)

        def send_direct():
            recipients = collect_recipients()
            if not recipients:
                messagebox.showwarning("Rundmail", "Bitte mindestens einen Empfänger auswählen oder manuell eintragen.", parent=dialog)
                return
            subject = subject_var.get().strip()
            if not subject:
                messagebox.showwarning("Rundmail", "Bitte einen Betreff erfassen.", parent=dialog)
                return
            first_doc = selected_docs[0] if selected_docs else doc_path_var.get().strip()
            if send_mode_var.get() in {"link", "attachment"} and not first_doc:
                messagebox.showerror("Anlage", "Bitte mindestens eine Datei auswählen oder Versandart 'Keine Anlage' verwenden.", parent=dialog)
                return
            if send_mode_var.get() == "link" and first_doc:
                try:
                    # Fehlende Links werden beim Direktversand automatisch erzeugt.
                    # Der Button "Downloadlinks erzeugen" bleibt nur Vorschau/Prüfung.
                    refresh_document_block(force_links=True)
                except Exception as exc:
                    messagebox.showerror("Nextcloud-Link", f"Der Downloadlink konnte nicht erstellt werden:\n{exc}", parent=dialog)
                    return
            payload = {
                "recipients": recipients,
                "subject": subject,
                "body": render_body(),
                "mode": send_mode_var.get(),
                "link": link_var.get().strip() if send_mode_var.get() == "link" else "",
                "local_file_path": first_doc if send_mode_var.get() in {"link", "attachment"} else "",
                "local_nextcloud_base": self.base_folder_var.get().strip(),
                "document_name": Path(first_doc).name if first_doc else "",
            }
            if send_mode_var.get() == "attachment":
                files_for_attachment = selected_docs if selected_docs else ([doc_path_var.get().strip()] if doc_path_var.get().strip() else [])
                if not files_for_attachment:
                    messagebox.showerror("Anlage", "Bitte mindestens eine Datei als Anlage auswählen.", parent=dialog)
                    return
                try:
                    attachments = []
                    total_size = 0
                    for file_path in files_for_attachment:
                        item = self.build_mail_attachment_payload(file_path)
                        if item:
                            attachments.append(item)
                            total_size += int(item.get("size", 0) or 0)
                    if not attachments:
                        raise ValueError("Es wurde keine gültige Anlage gefunden.")
                    if total_size > 12 * 1024 * 1024:
                        raise ValueError("Die Anlagen sind zusammen größer als 12 MB. Bitte besser als Nextcloud-Link versenden.")
                    payload["attachments"] = attachments
                    payload["attachment"] = attachments[0]
                except Exception as exc:
                    messagebox.showerror("Anlage", str(exc), parent=dialog)
                    return
            if not messagebox.askyesno("Rundmail senden", f"Rundmail jetzt an {len(recipients)} Empfänger senden?", parent=dialog):
                return
            try:
                response = self.api.send_mail(self.api_token, payload)
                sent = response.get("sent", 0)
                failed = response.get("failed", 0)
                messagebox.showinfo("Rundmail", f"Versand abgeschlossen.\nGesendet: {sent}\nFehler: {failed}", parent=dialog)
                app_log("info", "Rundmail direkt versendet", sent=sent, failed=failed)
            except Exception as exc:
                app_log_exception("Rundmail konnte nicht direkt versendet werden", exc)
                messagebox.showerror("Rundmail", f"Rundmail konnte nicht versendet werden:\n{exc}", parent=dialog)

        def preview_recipients():
            recipients = collect_recipients()
            preview = "\n".join(recipients) if recipients else "Keine Empfänger ausgewählt."
            messagebox.showinfo("Empfänger-Vorschau", f"Empfänger: {len(recipients)}\n\n{preview}", parent=dialog)

        def on_send_mode_changed(*_args):
            if send_mode_var.get() == "attachment":
                refresh_document_block(force_links=False)
            elif send_mode_var.get() == "none":
                link_var.set("")
                link_text.delete("1.0", "end")
        send_mode_var.trace_add("write", on_send_mode_changed)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=8, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Empfänger prüfen", command=preview_recipients).pack(side="left", padx=4)
        ttk.Button(buttons, text="Text kopieren", command=copy_mail_text).pack(side="left", padx=4)
        ttk.Button(buttons, text="Im Mailprogramm öffnen", command=open_mail_client).pack(side="left", padx=4)
        ttk.Button(buttons, text="Direkt versenden", command=send_direct).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)

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
            "document_date", "event", "place", "copyright_author", "rights_holder",
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
            ("Zeit / Ort / Inhalt", ["document_date", "event", "place", "description", "note"]),
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
        openai_points_var = tk.StringVar(value=str(self.config_data.get("openai_metadata_points", 2) or 2))
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
            openai_points_var.set("2")

        ttk.Button(openai_limits_frame, text="Standard", command=reset_openai_limits).pack(side="left")
        ttk.Label(openai_limits_frame, text="OpenAI-Punkte").pack(side="left", padx=(16, 0))
        ttk.Spinbox(openai_limits_frame, from_=0, to=50, textvariable=openai_points_var, width=6).pack(side="left", padx=(6, 0))
        ttk.Label(api_tab, text="Empfohlen: gpt-4o-mini. Für PDFs werden standardmäßig nur die ersten 10 Seiten und maximal 4000 Zeichen an OpenAI gegeben. Die OpenAI-Pauschalpunkte werden als Punkteregel openai_metadata gespeichert.", wraplength=760).grid(row=10, column=0, columnspan=4, sticky="w", pady=(0, 8))

        openai_test_status_var = tk.StringVar(value="OpenAI-Schlüssel nicht geprüft")
        openai_balance_var = tk.StringVar(value="Guthaben: n.v.")

        def load_openai_points_rule() -> None:
            if not self.api_token:
                return
            def run_load() -> None:
                try:
                    resp = self.api.list_point_rules(self.api_token, self._current_points_year())
                    for rule in resp.get("rules", []) or []:
                        if str(rule.get("rule_key", "")) == "openai_metadata":
                            self.after(0, lambda value=str(int(rule.get("points", 2) or 0)): openai_points_var.set(value))
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
        ttk.Label(links_tab, text="Das Datenbankpasswort und SMTP-Passwort liegen nur auf dem Server/API. Das FTP-Passwort wird lokal per Windows-DPAPI verschlüsselt. Die OpenAI-Pauschalpunkte ändern Sie unter Admin > Punkteregeln verwalten > openai_metadata.", wraplength=760).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 10))

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
            if self.api_token:
                try:
                    self.api.update_point_rules(self.api_token, self._current_points_year(), [{
                        "rule_key": "openai_metadata",
                        "label": "OpenAI-Metadaten übernommen",
                        "category": "metadata",
                        "points": openai_points,
                        "is_active": 1,
                    }])
                except Exception as exc:
                    messagebox.showwarning("OpenAI-Punkte", f"Einstellungen wurden lokal gespeichert, aber die OpenAI-Punkteregel konnte nicht gespeichert werden:\n{exc}", parent=dialog)
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

    def open_place_folder_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Die Ortsordner-Stammdaten sind nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Ortsordner-Stammdaten")
        try: self.track_window_geometry(dialog, "Ortsordner-Stammdaten")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("760x520")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        frame = ttk.LabelFrame(dialog, text="Ort → Ordner im Nextcloud-Stammverzeichnis", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=("place", "folder"), show="headings")
        tree.heading("place", text="Ort", anchor="w")
        tree.heading("folder", text="Ordner", anchor="w")
        tree.column("place", width=220, anchor="w")
        tree.column("folder", width=420, anchor="w")
        tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=4, sticky="ns")

        place_var = tk.StringVar()
        folder_var = tk.StringVar()
        ttk.Label(frame, text="Ort:").grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(frame, textvariable=place_var).grid(row=2, column=0, sticky="ew", padx=(0, 6))
        ttk.Label(frame, text="Ordner:").grid(row=1, column=1, sticky="w", pady=(8, 2))
        ttk.Entry(frame, textvariable=folder_var).grid(row=2, column=1, sticky="ew", padx=(0, 6))

        def load_rows():
            for item in tree.get_children():
                tree.delete(item)
            rows = []
            try:
                if self.api_token:
                    rows = self.api.list_place_folders(self.api_token).get("places", [])
            except ApiError as exc:
                messagebox.showerror("Ortsordner", f"Stammdaten konnten nicht geladen werden:\n{exc}", parent=dialog)
                rows = []
            for idx, row in enumerate(rows):
                tree.insert("", "end", iid=str(idx), values=(row.get("place", ""), row.get("folder_name", "")))

        def select_row(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if len(vals) >= 2:
                place_var.set(vals[0])
                folder_var.set(vals[1])

        def add_or_update():
            place = place_var.get().strip()
            folder = folder_var.get().strip()
            if not place or not folder:
                messagebox.showwarning("Unvollständig", "Bitte Ort und Ordner erfassen.", parent=dialog)
                return
            # In der Anzeige aktualisieren oder hinzufügen.
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                if vals and self.normalize_folder_token(vals[0]) == self.normalize_folder_token(place):
                    tree.item(iid, values=(place, folder))
                    return
            tree.insert("", "end", values=(place, folder))

        def delete_selected():
            for iid in tree.selection():
                tree.delete(iid)

        def save_rows():
            rows = []
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                if len(vals) >= 2 and str(vals[0]).strip() and str(vals[1]).strip():
                    rows.append({"place": str(vals[0]).strip(), "folder_name": str(vals[1]).strip()})
            try:
                self.api.update_place_folders(self.api_token, rows)
                self.place_folder_map = {self.normalize_folder_token(r["place"]): r["folder_name"] for r in rows}
                self.config_data["place_folder_map"] = self.place_folder_map
                save_config(self.config_data)
                self.load_writable_folders(show_message=False)
                messagebox.showinfo("Ortsordner", "Ortsordner-Stammdaten wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except ApiError as exc:
                messagebox.showerror("Ortsordner", str(exc), parent=dialog)

        ttk.Button(frame, text="Hinzufügen / Aktualisieren", command=add_or_update).grid(row=2, column=2, sticky="ew", padx=4)
        ttk.Button(frame, text="Entfernen", command=delete_selected).grid(row=2, column=3, sticky="ew", padx=4)
        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Speichern", command=save_rows).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        tree.bind("<<TreeviewSelect>>", select_row)
        load_rows()

    def update_archive_collection_references(self, old_values: list[str], new_value: str) -> int:
        old_keys = {str(value or "").strip().casefold() for value in old_values if str(value or "").strip()}
        if not old_keys:
            return 0
        replacement = str(new_value or "").strip()
        changed = 0
        try:
            items = load_metadata_files(self.metadata_folder_path())
        except Exception:
            items = []
        for item in items:
            current = str(item.get("archive_name") or item.get("archiv") or "").strip()
            if current.casefold() not in old_keys:
                continue
            item["archive_name"] = replacement
            item["archiv"] = replacement
            metadata_file = item.get("_metadata_file")
            if metadata_file:
                try:
                    save_metadata_file(Path(str(metadata_file)), item)
                    changed += 1
                except Exception as exc:
                    app_log_exception("Archiv/Sammlung konnte in Metadaten nicht vereinheitlicht werden", exc, metadata_file=str(metadata_file))
        return changed

    def open_archive_collection_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Archiv/Sammlung-Stammdaten sind nur für Superadmins sichtbar.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Archiv/Sammlung-Stammdaten")
        try: self.track_window_geometry(dialog, "Archiv/Sammlung-Stammdaten")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("720x520")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(dialog, text="Archiv/Sammlung-Stammdaten", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        tree = ttk.Treeview(dialog, columns=("name",), show="headings", selectmode="browse")
        tree.heading("name", text="Archiv / Sammlung", anchor="w")
        tree.column("name", width=640, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns", pady=6)

        value_var = tk.StringVar()
        form = ttk.Frame(dialog, padding=(10, 4))
        form.grid(row=2, column=0, columnspan=2, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Bezeichnung:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(form, textvariable=value_var).grid(row=0, column=1, sticky="ew")

        def load_rows() -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            for value in self.archive_collection_options():
                tree.insert("", "end", values=(value,))

        def selected_value() -> str:
            sel = tree.selection()
            if not sel:
                return ""
            return str(tree.item(sel[0], "values")[0] or "").strip()

        def select_row(_event=None) -> None:
            value_var.set(selected_value())

        def save_value() -> None:
            old = selected_value()
            new = value_var.get().strip()
            if not new:
                messagebox.showwarning("Archiv/Sammlung", "Bitte eine Bezeichnung erfassen.", parent=dialog)
                return
            values = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            if new.casefold() not in {value.casefold() for value in values}:
                values.append(new)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            changed = self.update_archive_collection_references([old], new) if old and old.casefold() != new.casefold() else 0
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            load_rows()
            messagebox.showinfo("Archiv/Sammlung", f"Gespeichert. Aktualisierte lokale Dokumentbezüge: {changed}", parent=dialog)

        def delete_value() -> None:
            old = selected_value()
            if not old:
                return
            if not messagebox.askyesno("Archiv/Sammlung", f"Eintrag aus der Auswahlliste entfernen?\n\n{old}\n\nDokumentbezüge bleiben unverändert.", parent=dialog):
                return
            self.config_data["archive_collection_options"] = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            value_var.set("")
            load_rows()

        def merge_value() -> None:
            old = selected_value()
            if not old:
                messagebox.showwarning("Archiv/Sammlung", "Bitte zuerst einen Eintrag auswählen.", parent=dialog)
                return
            target = simpledialog.askstring("Verschmelzen", f"'{old}' verschmelzen in welche Bezeichnung?", parent=dialog)
            target = str(target or "").strip()
            if not target:
                return
            values = [value for value in self.archive_collection_options() if value.casefold() != old.casefold()]
            if target.casefold() not in {value.casefold() for value in values}:
                values.append(target)
            values.sort(key=str.casefold)
            self.config_data["archive_collection_options"] = values
            changed = self.update_archive_collection_references([old], target)
            save_config(self.config_data)
            self.refresh_upload_metadata_option_comboboxes()
            value_var.set(target)
            load_rows()
            messagebox.showinfo("Archiv/Sammlung", f"Einträge verschmolzen. Aktualisierte lokale Dokumentbezüge: {changed}", parent=dialog)

        tree.bind("<<TreeviewSelect>>", select_row)
        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Speichern / Umbenennen", command=save_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Verschmelzen...", command=merge_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Aus Liste entfernen", command=delete_value).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        load_rows()

    def open_import_existing_files_dialog(self) -> None:
        """Importiert bereits manuell in Nextcloud abgelegte Dateien in JSON/API.

        Gedacht für Fälle, in denen Dateien z. B. per Explorer nach
        01_ABLAGE_ORTSCHRONIK kopiert wurden. Die Datei bleibt an Ort und Stelle,
        es werden nur Metadatensatz, JSON-Sicherung und MySQL-Datensatz angelegt.
        """
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Nur Superadmins können vorhandene Dateien einlesen.")
            return
        if not self.api_token:
            messagebox.showwarning("API", "Bitte zuerst an der API anmelden.")
            return
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            messagebox.showwarning("Nextcloud", "Bitte zuerst das Nextcloud-Stammverzeichnis in den Stammdaten festlegen.")
            return
        base = Path(base_text).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showwarning("Nextcloud", f"Nextcloud-Stammverzeichnis nicht gefunden:\n{base}")
            return

        # Für den Import sind Schreibrechte maßgeblich, weil ein neuer Metadatensatz angelegt wird.
        if not self.writable_folders:
            self.load_writable_folders(show_message=False)
        folders = [p for p in self.writable_folders if p.exists() and p.is_dir()]
        if not folders:
            messagebox.showwarning("Ordner", "Es wurden keine erlaubten Schreibordner gefunden.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Vorhandene Dateien einlesen")
        try: self.track_window_geometry(dialog, "Vorhandene Dateien einlesen")
        except Exception: pass
        dialog.geometry("860x620")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(3, weight=1)

        ttk.Label(dialog, text="Bereits vorhandene Dateien werden nicht verschoben. Es werden Metadaten/JSON und ein MySQL-Datensatz angelegt.", wraplength=820).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        top = ttk.Frame(dialog)
        top.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        top.columnconfigure(1, weight=1)
        folder_var = tk.StringVar()
        folder_map = {self.display_path_for_folder(p, base): p for p in folders}
        labels = sorted(folder_map.keys(), key=str.lower)
        preferred = next((label for label, p in folder_map.items() if p.name.upper() == "01_ABLAGE_ORTSCHRONIK"), None)
        folder_var.set(preferred or (labels[0] if labels else ""))
        ttk.Label(top, text="Ordner:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        folder_combo = ttk.Combobox(top, textvariable=folder_var, values=labels, state="readonly")
        folder_combo.grid(row=0, column=1, sticky="ew")
        recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Unterordner einbeziehen", variable=recursive_var).grid(row=0, column=2, sticky="w", padx=(12, 0))

        import_users: list[dict] = []
        user_label_var = tk.StringVar()
        user_map: dict[str, dict] = {}
        try:
            user_response = self.api.list_users(self.api_token)
            for user in user_response.get("users", []) or []:
                if int(user.get("is_active", user.get("active", 1)) or 0) != 1:
                    continue
                label = f"{user.get('display_name','')} ({user.get('username','')}) – {user.get('place','')}"
                user_map[label] = user
                import_users.append(user)
            current_label = next((label for label, u in user_map.items() if str(u.get('display_name','')) == self.display_name_var.get().strip()), None)
            user_label_var.set(current_label or (next(iter(user_map.keys()), "")))
        except Exception as exc:
            app_log_exception("Benutzerliste für Import konnte nicht geladen werden", exc)
        ttk.Label(top, text="Dateien sind von:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        user_combo = ttk.Combobox(top, textvariable=user_label_var, values=list(user_map.keys()), state="readonly")
        user_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))

        status_var = tk.StringVar(value="Noch nicht geprüft.")
        ttk.Label(dialog, textvariable=status_var).grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 4))

        columns = ("path", "document_type", "status")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", selectmode="extended")
        tree.heading("path", text="Datei")
        tree.heading("document_type", text="Dokumenttyp")
        tree.heading("status", text="Status")
        tree.column("path", width=560, anchor="w")
        tree.column("document_type", width=140, anchor="w")
        tree.column("status", width=120, anchor="w")
        tree.grid(row=3, column=0, sticky="nsew", padx=12, pady=6)
        ysb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        ysb.grid(row=3, column=1, sticky="ns", pady=6)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, sticky="ew", padx=12, pady=(6, 12))
        buttons.columnconfigure(0, weight=1)

        scan_results: list[Path] = []

        def load_known_paths() -> set[str]:
            known: set[str] = set()
            # lokale JSON-Sicherungen
            try:
                for item in load_metadata_files(self.metadata_folder_path()):
                    cp = item.get("current_path")
                    if cp:
                        known.add(str(Path(str(cp)).resolve()).lower())
            except Exception:
                pass
            # zentrale MySQL/API-Datensätze
            try:
                response = self.api.list_documents(self.api_token, only_own=False)
                for doc in response.get("documents", []) or []:
                    cp = doc.get("current_path")
                    if cp:
                        known.add(str(Path(str(cp)).resolve()).lower())
            except Exception as exc:
                app_log_exception("Bekannte Dokumentpfade konnten nicht vollständig geladen werden", exc)
            return known

        def is_relevant_file(path: Path) -> bool:
            if not path.is_file():
                return False
            if self.is_hidden_system_path(path):
                return False
            if any(str(part).upper() in {"_ARCHIV", "ARCHIV", "ARCHIVIERT", "ABGELEHNT", "GELOESCHT", "GELÖSCHT"} for part in path.parts):
                return False
            name = path.name
            if name.startswith("."):
                return False
            if name.lower().endswith(".metadata.json"):
                return False
            if any(part.startswith(".ortschronik_") for part in path.parts):
                return False
            return True

        def scan() -> None:
            nonlocal scan_results
            for iid in tree.get_children():
                tree.delete(iid)
            scan_results = []
            label = folder_var.get()
            root = folder_map.get(label)
            if not root or not root.exists():
                status_var.set("Ordner nicht gefunden.")
                return
            known = load_known_paths()
            iterator = root.rglob("*") if recursive_var.get() else root.iterdir()
            try:
                for path in sorted(iterator, key=lambda p: str(p).lower()):
                    if not is_relevant_file(path):
                        continue
                    key = str(path.resolve()).lower()
                    if key in known:
                        continue
                    scan_results.append(path)
                    rel = self.display_path_for_folder(path, base)
                    tree.insert("", "end", iid=str(path), values=(rel, detect_document_type(path), "neu"))
            except Exception as exc:
                app_log_exception("Import-Scan fehlgeschlagen", exc)
                messagebox.showerror("Einlesen", f"Der Ordner konnte nicht vollständig durchsucht werden:\n{exc}", parent=dialog)
            status_var.set(f"{len(scan_results)} neue Datei(en) gefunden.")

        def import_selected() -> None:
            selected = [Path(iid) for iid in tree.selection()]
            if not selected:
                messagebox.showinfo("Einlesen", "Bitte zuerst Dateien auswählen.", parent=dialog)
                return
            owner = user_map.get(user_label_var.get().strip()) or {}
            owner_id = int(owner.get("id", 0) or 0)
            display_name = str(owner.get("display_name") or self.display_name_var.get().strip() or "Admin")
            owner_place = str(owner.get("place") or self.place_var.get().strip())
            if not owner_id:
                messagebox.showwarning("Benutzerzuordnung", "Bitte auswählen, von wem die Dateien sind.", parent=dialog)
                return
            imported = 0
            failed = 0
            for path in selected:
                try:
                    upload_id = make_upload_id()
                    now = datetime.now().isoformat(timespec="seconds")
                    item = {
                        "upload_id": upload_id,
                        "original_filename": path.name,
                        "stored_filename": path.name,
                        "current_filename": path.name,
                        "current_path": str(path),
                        "target_folder": str(path.parent),
                        "uploaded_by": display_name,
                        "import_uploaded_by_user_id": owner_id,
                        "uploaded_at": now,
                        "status": "erfasst",
                        "odv_capture_mode": "existing_file_metadata",
                        "odv_captured_by_admin": True,
                        "document_type": detect_document_type(path),
                        "source": "",
                        "original_location": "",
                        "document_date": "",
                        "event": "",
                        "place": owner_place,
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
                    }
                    append_metadata_history(item, display_name, "Vorhandene Nextcloud-Datei in ODV erfasst", str(path))
                    metadata_file = self.metadata_folder_path() / f"{upload_id}.metadata.json"
                    save_metadata_file(metadata_file, item)
                    item["_metadata_file"] = str(metadata_file)
                    self.api.create_document(self.api_token, self.document_create_payload_from_item(item))
                    add_history(HistoryEntry.now(display_name, "Vorhandene Nextcloud-Datei in ODV erfasst", str(path), upload_id))
                    imported += 1
                    try:
                        tree.set(str(path), "status", "eingelesen")
                    except Exception:
                        pass
                except Exception as exc:
                    failed += 1
                    app_log_exception("Vorhandene Datei konnte nicht eingelesen werden", exc)
                    try:
                        tree.set(str(path), "status", "Fehler")
                    except Exception:
                        pass
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            messagebox.showinfo("Einlesen", f"Eingelesen: {imported}\nFehler: {failed}", parent=dialog)
            scan()

        ttk.Button(buttons, text="Ausgewählte einlesen", command=import_selected).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).grid(row=0, column=2, sticky="e", padx=(8, 0))
        folder_combo.bind("<<ComboboxSelected>>", lambda _e: scan())

        scan()

    def open_local_backup_cleanup_dialog(self) -> None:
        """Prüft lokale JSON-Sicherungsdateien gegen die zentrale MySQL/API-Liste.

        Im Produktivmodus sind JSON-Dateien nur Sicherung. Dieser Dialog hilft,
        verwaiste lokale Sicherungen zu finden, die keinen passenden MySQL-
        Datensatz mehr besitzen, und sie gezielt zu verschieben oder zu löschen.
        """
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Lokale Sicherungsdateien prüfen/bereinigen")
        try: self.track_window_geometry(dialog, "Lokale Sicherungsdateien prüfen/bereinigen")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("1150x620")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        info = ttk.Label(
            dialog,
            text=(
                "Lokale JSON-Dateien sind nur Sicherung. Dateien bearbeiten zeigt im Produktivmodus ausschließlich MySQL/API-Datensätze.\n"
                "Verwaiste Sicherungen sind JSON-Dateien ohne passenden MySQL-Datensatz. Sie können verschoben oder gelöscht werden."
            ),
            wraplength=1050,
        )
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        frame = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            frame,
            columns=("status", "upload_id", "file", "json_file"),
            show="headings",
            selectmode="extended",
        )
        for col, label, width in [
            ("status", "Status", 120),
            ("upload_id", "Upload-ID", 210),
            ("file", "Datei", 260),
            ("json_file", "JSON-Datei", 520),
        ]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.tag_configure("orphan", background="#ffe0e0")
        tree.tag_configure("ok", background="#e8f5e9")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        status_var = tk.StringVar(value="Noch nicht geprüft.")
        ttk.Label(dialog, textvariable=status_var).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))

        rows_by_iid: dict[str, dict] = {}

        def load_backup_rows() -> None:
            rows_by_iid.clear()
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                response = self.api.list_documents(self.api_token, only_own=False)
                api_ids = {str(doc.get("upload_id", "")) for doc in response.get("documents", []) if doc.get("upload_id")}
            except ApiError as exc:
                messagebox.showerror("API", f"MySQL/API-Dokumentliste konnte nicht geladen werden:\n{exc}", parent=dialog)
                return

            folder = self.metadata_folder_path()
            local_items = load_metadata_files(folder)
            orphan_count = 0
            ok_count = 0
            for idx, item in enumerate(local_items):
                upload_id = str(item.get("upload_id", "") or "")
                json_file = str(item.get("_metadata_file", "") or "")
                filename = str(item.get("current_filename") or item.get("stored_filename") or item.get("original_filename") or "")
                exists_in_api = bool(upload_id and upload_id in api_ids)
                status = "in MySQL vorhanden" if exists_in_api else "verwaist"
                tag = "ok" if exists_in_api else "orphan"
                if exists_in_api:
                    ok_count += 1
                else:
                    orphan_count += 1
                iid = f"row-{idx}"
                tree.insert("", "end", iid=iid, values=(status, upload_id, filename, json_file), tags=(tag,))
                rows_by_iid[iid] = item
            status_var.set(f"{len(local_items)} JSON-Sicherungen geprüft: {ok_count} vorhanden, {orphan_count} verwaist.")

        def selected_orphans() -> list[dict]:
            result = []
            for iid in tree.selection():
                item = rows_by_iid.get(iid)
                if not item:
                    continue
                vals = tree.item(iid, "values")
                if vals and vals[0] == "verwaist":
                    result.append({"iid": iid, "item": item})
            return result

        def move_selected_orphans() -> None:
            selected = selected_orphans()
            if not selected:
                messagebox.showinfo("Bereinigung", "Bitte zuerst verwaiste JSON-Dateien auswählen.", parent=dialog)
                return
            target_dir = self.metadata_folder_path() / "_verwaiste_sicherungen"
            target_dir.mkdir(parents=True, exist_ok=True)
            moved = 0
            errors = []
            for row in selected:
                item = row["item"]
                source = Path(str(item.get("_metadata_file", "") or ""))
                if not source.exists():
                    errors.append(f"Nicht gefunden: {source}")
                    continue
                target = target_dir / source.name
                counter = 1
                while target.exists():
                    target = target_dir / f"{source.stem}_{counter}{source.suffix}"
                    counter += 1
                try:
                    source.rename(target)
                    moved += 1
                except Exception as exc:
                    errors.append(f"{source}: {exc}")
            app_log("info", "Verwaiste JSON-Sicherungen verschoben", count=moved, target=str(target_dir))
            load_backup_rows()
            msg = f"{moved} verwaiste Sicherungsdatei(en) verschoben nach:\n{target_dir}"
            if errors:
                msg += "\n\nFehler:\n" + "\n".join(errors[:5])
            messagebox.showinfo("Bereinigung", msg, parent=dialog)

        def delete_selected_orphans() -> None:
            selected = selected_orphans()
            if not selected:
                messagebox.showinfo("Bereinigung", "Bitte zuerst verwaiste JSON-Dateien auswählen.", parent=dialog)
                return
            if not messagebox.askyesno(
                "Verwaiste Sicherungen löschen",
                f"{len(selected)} verwaiste JSON-Sicherungsdatei(en) endgültig löschen?\n\n"
                "Sicherer ist meist zuerst 'Verschieben'.",
                parent=dialog,
            ):
                return
            deleted = 0
            errors = []
            for row in selected:
                item = row["item"]
                source = Path(str(item.get("_metadata_file", "") or ""))
                try:
                    if source.exists():
                        source.unlink()
                        deleted += 1
                except Exception as exc:
                    errors.append(f"{source}: {exc}")
            app_log("info", "Verwaiste JSON-Sicherungen gelöscht", count=deleted)
            load_backup_rows()
            msg = f"{deleted} verwaiste Sicherungsdatei(en) gelöscht."
            if errors:
                msg += "\n\nFehler:\n" + "\n".join(errors[:5])
            messagebox.showinfo("Bereinigung", msg, parent=dialog)

        buttons = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(buttons, text="Aktualisieren", command=load_backup_rows).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Ausgewählte verwaiste verschieben", command=move_selected_orphans).pack(side="left", padx=6)
        ttk.Button(buttons, text="Ausgewählte verwaiste löschen", command=delete_selected_orphans).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_backup_rows()

    def open_sessions_devices_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Sitzungen und Geräte", "Nur Superadmins können Sitzungen und Geräte verwalten.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Sitzungen und Geräte")
        try: self.track_window_geometry(dialog, "Sitzungen und Geräte")
        except Exception: pass
        dialog.geometry("1100x620")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        nb = ttk.Notebook(dialog)
        nb.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        sess_frame = ttk.Frame(nb, padding=8)
        dev_frame = ttk.Frame(nb, padding=8)
        nb.add(sess_frame, text="Aktive Sitzungen")
        nb.add(dev_frame, text="Geräte")
        for f in (sess_frame, dev_frame):
            f.columnconfigure(0, weight=1)
            f.rowconfigure(0, weight=1)

        sess_cols = ("id", "user", "device", "app", "ip", "started", "last", "expires")
        sess_tree = ttk.Treeview(sess_frame, columns=sess_cols, show="headings")
        for col, label, width in [
            ("id", "ID", 60), ("user", "Benutzer", 190), ("device", "Gerät", 190),
            ("app", "ODV", 80), ("ip", "IP", 130), ("started", "Start", 145),
            ("last", "Letzte Aktivität", 145), ("expires", "Gültig bis", 145),
        ]:
            sess_tree.heading(col, text=label, anchor="w")
            sess_tree.column(col, width=width, anchor="w")
        sess_tree.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(sess_frame, orient="vertical", command=sess_tree.yview).grid(row=0, column=1, sticky="ns")

        dev_cols = ("user_id", "user", "device_id", "device", "windows", "app", "ip", "first", "last", "blocked")
        dev_tree = ttk.Treeview(dev_frame, columns=dev_cols, show="headings")
        for col, label, width in [
            ("user_id", "User-ID", 70), ("user", "Benutzer", 190), ("device_id", "Geräte-ID", 220),
            ("device", "Gerät", 170), ("windows", "Windows-Benutzer", 140), ("app", "ODV", 80),
            ("ip", "IP", 120), ("first", "Erstmalig", 145), ("last", "Letzter Login", 145), ("blocked", "Gesperrt", 80),
        ]:
            dev_tree.heading(col, text=label, anchor="w")
            dev_tree.column(col, width=width, anchor="w")
        dev_tree.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(dev_frame, orient="vertical", command=dev_tree.yview).grid(row=0, column=1, sticky="ns")

        state = {"devices": [], "sessions": []}

        def refresh():
            try:
                data = self.api.list_sessions_and_devices(self.api_token)
                state["devices"] = list(data.get("devices", []))
                state["sessions"] = list(data.get("sessions", []))
            except ApiError as exc:
                messagebox.showerror("Sitzungen und Geräte", f"Daten konnten nicht geladen werden:\n{exc}", parent=dialog)
                return
            for tree in (sess_tree, dev_tree):
                for iid in tree.get_children():
                    tree.delete(iid)
            for row in state["sessions"]:
                sess_tree.insert("", "end", iid=str(row.get("session_id")), values=(
                    row.get("session_id", ""), row.get("display_name", ""), row.get("device_name", ""),
                    row.get("app_version", ""), row.get("ip_address", ""), row.get("started_at", ""),
                    row.get("last_seen_at", ""), row.get("expires_at", ""),
                ))
            for idx, row in enumerate(state["devices"]):
                dev_tree.insert("", "end", iid=str(idx), values=(
                    row.get("user_id", ""), row.get("display_name", ""), row.get("device_id", ""),
                    row.get("device_name", ""), row.get("windows_user", ""), row.get("app_version", ""),
                    row.get("last_ip", ""), row.get("first_seen_at", ""), row.get("last_login_at", ""),
                    "ja" if int(row.get("is_blocked", 0) or 0) == 1 else "nein",
                ))

        def end_selected_session():
            sel = sess_tree.selection()
            if not sel:
                messagebox.showinfo("Sitzung beenden", "Bitte eine Sitzung auswählen.", parent=dialog)
                return
            sid = int(sel[0])
            if not messagebox.askyesno("Sitzung beenden", f"Sitzung {sid} wirklich beenden?", parent=dialog):
                return
            try:
                self.api.end_session(self.api_token, sid)
                refresh()
            except ApiError as exc:
                messagebox.showerror("Sitzung beenden", str(exc), parent=dialog)

        def selected_device() -> dict | None:
            sel = dev_tree.selection()
            if not sel:
                return None
            try:
                return state["devices"][int(sel[0])]
            except Exception:
                return None

        def set_blocked(blocked: bool):
            row = selected_device()
            if not row:
                messagebox.showinfo("Gerät", "Bitte ein Gerät auswählen.", parent=dialog)
                return
            action = "sperren" if blocked else "freigeben"
            if not messagebox.askyesno("Gerät", f"Gerät für {row.get('display_name','Benutzer')} wirklich {action}?", parent=dialog):
                return
            try:
                self.api.set_device_blocked(self.api_token, int(row.get("user_id")), str(row.get("device_id")), blocked)
                refresh()
            except ApiError as exc:
                messagebox.showerror("Gerät", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Aktualisieren", command=refresh).pack(side="left")
        ttk.Button(buttons, text="Ausgewählte Sitzung beenden", command=end_selected_session).pack(side="left", padx=8)
        ttk.Button(buttons, text="Gerät sperren", command=lambda: set_blocked(True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Gerät freigeben", command=lambda: set_blocked(False)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        refresh()

    def open_user_management_dialog(self) -> None:
        if not role_allows_user_management(self.current_role()):
            messagebox.showwarning("Keine Berechtigung", "Die Benutzerverwaltung ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("Benutzerverwaltung", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Benutzerverwaltung")
        try: self.track_window_geometry(dialog, "Benutzerverwaltung")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("1180x620")
        dialog.columnconfigure(0, weight=0)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(dialog, text="Benutzer anlegen / bearbeiten", padding=10)
        form.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        form.columnconfigure(1, weight=1)

        list_frame = ttk.LabelFrame(dialog, text="Benutzerliste aus MySQL / API", padding=10)
        list_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        name_var = tk.StringVar()
        username_var = tk.StringVar()
        email_var = tk.StringVar()
        password_var = tk.StringVar()
        role_var = tk.StringVar(value="Ortschronist")
        place_var = tk.StringVar()
        active_var = tk.BooleanVar(value=True)
        selected_user_id = {"id": None}
        api_users: list[dict] = []

        labels = [
            ("Name:", name_var),
            ("Benutzername:", username_var),
            ("E-Mail:", email_var),
            ("Passwort:", password_var),
            ("Rolle:", role_var),
            ("Ort des Ortschronisten:", place_var),
        ]
        for row, (label, var) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if label == "Rolle:":
                ttk.Combobox(form, textvariable=var, values=ROLES, state="readonly", width=28).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
            elif label == "Passwort:":
                pw_frame = ttk.Frame(form)
                pw_frame.grid(row=row, column=1, sticky="ew", padx=6, pady=5)
                pw_frame.columnconfigure(0, weight=1)
                password_entry = ttk.Entry(pw_frame, textvariable=var, show="*", width=34)
                password_entry.grid(row=0, column=0, sticky="ew")
                def _show_password(_e=None, entry=password_entry):
                    entry.configure(show="")
                def _hide_password(_e=None, entry=password_entry):
                    entry.configure(show="*")
                eye_btn = ttk.Button(pw_frame, text="👁", width=3)
                eye_btn.grid(row=0, column=1, padx=(4, 0))
                eye_btn.bind("<ButtonPress-1>", _show_password)
                eye_btn.bind("<ButtonRelease-1>", _hide_password)
                eye_btn.bind("<Leave>", _hide_password)
            else:
                ttk.Entry(form, textvariable=var, width=34).grid(row=row, column=1, sticky="ew", padx=6, pady=5)

        ttk.Checkbutton(form, text="Benutzer aktiv", variable=active_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 4))
        hint = ttk.Label(
            form,
            text=(
                "Die Benutzerverwaltung arbeitet jetzt direkt mit der zentralen MySQL-Datenbank über die API.\n"
                "Passwort leer lassen = bestehendes Passwort beibehalten. Bei neuen Benutzern ist ein Passwort Pflicht."
            ),
            wraplength=360,
        )
        hint.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 12))

        perm_frame = ttk.LabelFrame(form, text="Rechte / Hinweise", padding=6)
        perm_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        perm_frame.columnconfigure(0, weight=1)
        permission_vars: dict[str, tuple[tk.BooleanVar, tk.BooleanVar]] = {}
        ttk.Label(perm_frame, text="Bereich").grid(row=0, column=0, sticky="w")
        ttk.Label(perm_frame, text="lesen").grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(perm_frame, text="schreiben").grid(row=0, column=2, sticky="w", padx=8)
        for idx, (group_key, group_label) in enumerate(self.FOLDER_GROUPS, start=1):
            read_var = tk.BooleanVar(value=False)
            write_var = tk.BooleanVar(value=False)
            permission_vars[group_key] = (read_var, write_var)
            ttk.Label(perm_frame, text=group_label).grid(row=idx, column=0, sticky="w", pady=2)
            ttk.Checkbutton(perm_frame, variable=read_var).grid(row=idx, column=1, sticky="w", padx=8)
            ttk.Checkbutton(perm_frame, variable=write_var).grid(row=idx, column=2, sticky="w", padx=8)

        tree = ttk.Treeview(list_frame, columns=("name", "username", "email", "role", "place", "active", "last_login"), show="headings")
        for col, label, width in [
            ("name", "Name", 220),
            ("username", "Benutzername", 150),
            ("email", "E-Mail", 220),
            ("role", "Rolle", 120),
            ("place", "Ort", 140),
            ("active", "Aktiv", 70),
            ("last_login", "Letzter Login", 150),
        ]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        def api_role_label(role: str) -> str:
            return self.api_role_to_local(role)

        def default_permission_values(role_label: str) -> dict[str, dict[str, bool]]:
            if role_label in ("Admin", "Superadmin"):
                return {key: {"read": True, "write": True} for key, _ in self.FOLDER_GROUPS}
            return {
                "00_ORTSCHRONIK": {"read": True, "write": False},
                "01_ABLAGE_ORTSCHRONIK": {"read": True, "write": True},
                "02_AUSTAUSCH": {"read": True, "write": True},
                "03_INFORMATION": {"read": True, "write": False},
                "05_ORGA_CHRONISTEN": {"read": False, "write": False},
                "06_UNSERE_ARBEITEN": {"read": True, "write": True},
                "OWN_PLACE_FOLDER": {"read": True, "write": True},
                "OTHER_PLACE_FOLDERS": {"read": False, "write": False},
            }

        def set_permission_widgets(perms: dict[str, dict[str, bool]]) -> None:
            for key, (read_var, write_var) in permission_vars.items():
                row = perms.get(key, {"read": False, "write": False})
                read_var.set(bool(row.get("read", False)))
                write_var.set(bool(row.get("write", False)))

        def current_permission_payload() -> list[dict]:
            rows = []
            for key, (read_var, write_var) in permission_vars.items():
                rows.append({
                    "folder_group": key,
                    "can_read": bool(read_var.get()),
                    "can_write": bool(write_var.get()),
                })
            return rows

        def load_user_permissions(user_id: int, role_label: str) -> None:
            set_permission_widgets(default_permission_values(role_label))
            try:
                response = self.api.get_folder_permissions(self.api_token, user_id)
                perms = {}
                for row in response.get("permissions", []):
                    key = str(row.get("folder_group", "")).strip()
                    if key:
                        perms[key] = {
                            "read": bool(int(row.get("can_read", 0) or 0)),
                            "write": bool(int(row.get("can_write", 0) or 0)),
                        }
                if perms:
                    set_permission_widgets(perms)
            except ApiError as exc:
                app_log_exception("Logout über API fehlgeschlagen", exc)

        def clear_form():
            selected_user_id["id"] = None
            name_var.set("")
            username_var.set("")
            email_var.set("")
            password_var.set("")
            role_var.set("Ortschronist")
            place_var.set("")
            active_var.set(True)
            set_permission_widgets(default_permission_values("Ortschronist"))
            try:
                tree.selection_remove(tree.selection())
            except tk.TclError:
                pass

        def refresh_tree(select_id: int | None = None):
            nonlocal api_users
            try:
                response = self.api.list_users(self.api_token)
                api_users = list(response.get("users", []))
            except ApiError as exc:
                messagebox.showerror("Benutzerverwaltung", f"Benutzer konnten nicht geladen werden:\n{exc}", parent=dialog)
                return

            for item in tree.get_children():
                tree.delete(item)
            for user in api_users:
                uid = str(user.get("id"))
                tree.insert("", "end", iid=uid, values=(
                    user.get("display_name", ""),
                    user.get("username", ""),
                    user.get("email", "") or "",
                    api_role_label(str(user.get("role", ""))),
                    user.get("place", "") or "",
                    "ja" if int(user.get("is_active", 0) or 0) == 1 else "nein",
                    user.get("last_login_at", "") or "",
                ))
            if select_id is not None and tree.exists(str(select_id)):
                tree.selection_set(str(select_id))
                tree.see(str(select_id))
                load_selected()

        def find_loaded_user(user_id: int) -> dict | None:
            for user in api_users:
                if int(user.get("id", 0)) == int(user_id):
                    return user
            return None

        def load_selected(_event=None):
            sel = tree.selection()
            if not sel:
                return
            user_id = int(sel[0])
            selected_user_id["id"] = user_id
            user = find_loaded_user(user_id)
            if not user:
                return
            name_var.set(user.get("display_name", ""))
            username_var.set(user.get("username", ""))
            email_var.set(user.get("email", "") or "")
            password_var.set("")
            role_var.set(api_role_label(str(user.get("role", "ortschronist"))))
            place_var.set(user.get("place", "") or "")
            active_var.set(int(user.get("is_active", 0) or 0) == 1)
            load_user_permissions(user_id, role_var.get())

        def build_payload(include_password: bool) -> dict:
            name = name_var.get().strip()
            username = normalize_username(username_var.get().strip())
            password = password_var.get()
            role = role_var.get().strip() or "Ortschronist"
            place = place_var.get().strip()
            if not name:
                raise ValueError("Bitte den vollständigen Namen erfassen.")
            if not username:
                raise ValueError("Bitte einen Login-Benutzernamen erfassen.")
            payload = {
                "display_name": name,
                "username": username,
                "email": email_var.get().strip(),
                "role": self.local_role_to_api(role),
                "place": place,
                "is_active": bool(active_var.get()),
            }
            if include_password:
                if not password:
                    raise ValueError("Bitte für neue Benutzer ein Passwort erfassen.")
                payload["password"] = password
            elif password:
                payload["password"] = password
            return payload

        def save_user():
            user_id = selected_user_id.get("id")
            try:
                if user_id is None:
                    payload = build_payload(include_password=True)
                    response = self.api.create_user(self.api_token, payload)
                    new_id = int(response.get("user_id", 0) or 0)
                    if new_id:
                        self.api.update_folder_permissions(self.api_token, new_id, current_permission_payload())
                    messagebox.showinfo("Benutzerverwaltung", "Benutzer wurde in der zentralen Datenbank angelegt.", parent=dialog)
                    refresh_tree(select_id=new_id or None)
                else:
                    payload = build_payload(include_password=False)
                    # Schutz gegen Selbst-Deaktivierung: Der angemeldete Benutzer darf
                    # sich nicht versehentlich über die Benutzerverwaltung deaktivieren.
                    current_username = normalize_username(self.username_var.get().strip())
                    edited_username = normalize_username(username_var.get().strip())
                    if edited_username == current_username and not bool(payload.get("is_active", True)):
                        active_var.set(True)
                        messagebox.showwarning(
                            "Nicht möglich",
                            "Der aktuell angemeldete Benutzer kann sich nicht selbst deaktivieren.",
                            parent=dialog,
                        )
                        return
                    self.api.update_user(self.api_token, int(user_id), payload)
                    self.api.update_folder_permissions(self.api_token, int(user_id), current_permission_payload())
                    messagebox.showinfo("Benutzerverwaltung", "Benutzer wurde in der zentralen Datenbank gespeichert.", parent=dialog)
                    refresh_tree(select_id=int(user_id))
                add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Benutzerverwaltung API", f"{name_var.get().strip()} / {username_var.get().strip()}"))
                self.refresh_history()
            except ValueError as exc:
                messagebox.showwarning("Benutzerverwaltung", str(exc), parent=dialog)
            except ApiError as exc:
                messagebox.showerror("Benutzerverwaltung", str(exc), parent=dialog)

        def deactivate_user():
            user_id = selected_user_id.get("id")
            if user_id is None:
                messagebox.showwarning("Keine Auswahl", "Bitte zuerst einen Benutzer auswählen.", parent=dialog)
                return
            if username_var.get().strip() == self.username_var.get().strip():
                messagebox.showwarning("Nicht möglich", "Der aktuell angemeldete Benutzer kann nicht deaktiviert werden.", parent=dialog)
                return
            if not messagebox.askyesno("Benutzer deaktivieren", "Soll der ausgewählte Benutzer wirklich deaktiviert werden?", parent=dialog):
                return
            try:
                payload = build_payload(include_password=False)
                payload["is_active"] = False
                self.api.update_user(self.api_token, int(user_id), payload)
                active_var.set(False)
                refresh_tree(select_id=int(user_id))
                add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Benutzer deaktiviert API", username_var.get().strip()))
                self.refresh_history()
            except (ValueError, ApiError) as exc:
                messagebox.showerror("Benutzerverwaltung", str(exc), parent=dialog)

        btns = ttk.Frame(form)
        btns.grid(row=9, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Button(btns, text="Neu", command=clear_form).pack(side="left", padx=4)
        ttk.Button(btns, text="Benutzer speichern", command=save_user).pack(side="left", padx=4)
        ttk.Button(btns, text="Benutzer deaktivieren", command=deactivate_user).pack(side="left", padx=4)
        ttk.Button(btns, text="Liste aktualisieren", command=lambda: refresh_tree()).pack(side="left", padx=4)

        tree.bind("<<TreeviewSelect>>", load_selected)
        refresh_tree()
        if tree.get_children():
            first = tree.get_children()[0]
            tree.selection_set(first)
            load_selected()

    # Konfiguration / Ordner
    def save_basic_config(self, show_message: bool = True) -> None:
        # Name, Benutzername, Rolle und Ort kommen aus der Benutzerverwaltung.
        # Hier speichern wir nur lokale Stammdaten wie Nextcloud-Stammverzeichnis.
        self.config_data["display_name"] = self.display_name_var.get().strip() or "Ortschronist/in"
        self.config_data["current_username"] = self.username_var.get().strip()
        self.config_data["current_role"] = self.role_var.get().strip() or "Ortschronist"
        self.config_data["current_place"] = self.place_var.get().strip()
        self.config_data["nextcloud_base_folder"] = self.normalize_local_path_text(self.base_folder_var.get().strip())
        self.base_folder_var.set(self.config_data["nextcloud_base_folder"])
        self.ensure_standard_metadata_folder()
        self.config_data["metadata_folder"] = self.metadata_folder_var.get().strip()
        save_config(self.config_data)
        self.apply_selected_user()
        if show_message:
            messagebox.showinfo("Gespeichert", "Stammdaten wurden gespeichert.")

    def choose_base_folder(self, parent: tk.Toplevel | None = None) -> None:
        folder = filedialog.askdirectory(title="Nextcloud-Stammverzeichnis auswählen", parent=parent or self)
        if folder:
            self.base_folder_var.set(self.normalize_local_path_text(folder))
            self.ensure_standard_metadata_folder()
            self.save_basic_config(show_message=False)
            self.load_writable_folders()

    def choose_metadata_folder(self) -> None:
        folder = filedialog.askdirectory(title="Zentralen Metadaten-Ordner auswählen")
        if folder:
            self.metadata_folder_var.set(self.normalize_local_path_text(folder))
            self.save_basic_config()


    def ensure_standard_metadata_folder(self) -> None:
        if not hasattr(self, "metadata_folder_var") or not hasattr(self, "base_folder_var"):
            return
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            self.metadata_folder_var.set("")
            self.config_data["metadata_folder"] = ""
            return
        folder_name = self.config_data.get("metadata_folder_name", ".ortschronik_metadaten") or ".ortschronik_metadaten"
        folder_name = str(folder_name).strip().replace("/", "_").replace("\\", "_")
        if not folder_name.startswith("."):
            folder_name = "." + folder_name
        self.config_data["metadata_folder_name"] = folder_name
        default_folder = Path(base_text).expanduser() / folder_name
        self.metadata_folder_var.set(self.normalize_local_path_text(default_folder))
        self.config_data["metadata_folder"] = self.normalize_local_path_text(default_folder)

    def set_default_metadata_folder(self, show_message: bool = True) -> None:
        base = Path(self.base_folder_var.get().strip()).expanduser()
        if not str(base).strip():
            messagebox.showwarning("Kein Basisordner", "Bitte zuerst den Nextcloud-Basisordner auswählen.")
            return
        self.ensure_standard_metadata_folder()
        default_folder = Path(self.metadata_folder_var.get().strip())
        save_config(self.config_data)
        if show_message:
            messagebox.showinfo("Metadaten-Ordner", f"Standard-Metadatenordner gesetzt:\n{default_folder}")

    def nextcloud_base_path(self, show_message: bool = False) -> Path | None:
        """Liefert das konfigurierte lokale Nextcloud-Stammverzeichnis.

        Wichtig für PyInstaller/EXE: Ein leerer Pfad darf niemals als aktueller
        Programmordner interpretiert werden, sonst erscheinen _internal, PIL,
        pypdf usw. in der Zielordnerauswahl.
        """
        base_text = self.base_folder_var.get().strip() if hasattr(self, "base_folder_var") else ""
        if not base_text:
            if show_message:
                messagebox.showwarning("Nextcloud-Stammverzeichnis", "Bitte zuerst unter Datei > Stammdaten das lokale Nextcloud-Stammverzeichnis auswählen.")
            return None
        base = Path(base_text).expanduser()
        try:
            base = base.resolve()
        except Exception:
            pass
        if not base.exists() or not base.is_dir():
            if show_message:
                messagebox.showwarning("Nextcloud-Stammverzeichnis", f"Das eingestellte Nextcloud-Stammverzeichnis wurde nicht gefunden:\n{base}")
            return None
        # Schutz gegen versehentliches Scannen des EXE-/Programmordners.
        try:
            forbidden_names = {"_internal", "app", "pypdf", "PIL", "tk_data", "tcl", "tcl8", "python"}
            child_names = {c.name for c in base.iterdir() if c.is_dir()}
            if "_internal" in child_names and ("app" in child_names or "pypdf" in child_names or "PIL" in child_names):
                if show_message:
                    messagebox.showwarning(
                        "Nextcloud-Stammverzeichnis",
                        "Das eingestellte Verzeichnis sieht wie der Programmordner der EXE aus, nicht wie der Nextcloud-Stammordner.\n\n"
                        "Bitte unter Datei > Stammdaten den Ordner z. B. C:\\Nextcloud_OC auswählen."
                    )
                return None
        except Exception:
            pass
        return base

    def load_folders_from_config(self) -> None:
        if self.nextcloud_base_path(show_message=False):
            self.load_writable_folders(show_message=False)

    def display_path_for_folder(self, path: Path, base: Path) -> str:
        try:
            rel = path.relative_to(base)
            return self.normalize_local_path_text(base) if str(rel) == "." else self.normalize_local_path_text(rel)
        except ValueError:
            return str(path)

    def choose_upload_target_tree(self) -> None:
        """Zielordner für Upload komfortabel als Baum auswählen."""
        if self.nextcloud_base_path(show_message=True) is None:
            return
        if not self.writable_folders:
            self.load_writable_folders(show_message=False)
        selected = self.open_folder_tree_dialog("Zielordner Nextcloud auswählen", self.writable_folders, self.target_folder_var.get())
        if selected:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            display = self.display_path_for_folder(selected, base)
            self.target_folder_map[display] = selected
            values = list(self.target_combo["values"])
            if display not in values:
                values.append(display)
                values.sort(key=str.lower)
                self.target_combo["values"] = values
            self.target_folder_var.set(display)

    def select_combobox_path(self, var: tk.StringVar, combo: ttk.Combobox, mapping: dict[str, Path], path: Path) -> None:
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        display = self.display_path_for_folder(path, base)
        mapping[display] = path
        values = list(combo["values"])
        if display not in values:
            values.append(display)
            values.sort(key=str.lower)
            combo["values"] = values
        var.set(display)

    def is_path_under_base(self, path: Path, base: Path) -> bool:
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    def open_folder_tree_dialog(self, title: str, folders: list[Path], current_display: str = "") -> Path | None:
        """Öffnet einen modalen Baumdialog für beschreibbare Zielordner.

        Kontextordner werden angezeigt, wenn darunter beschreibbare Ordner liegen.
        Auswählbar sind nur tatsächlich beschreibbare Ordner aus ``folders``.
        """
        base = self.nextcloud_base_path(show_message=True)
        if base is None:
            return None
        writable = {str(Path(f).resolve()) for f in folders if Path(f).exists() and self.is_path_under_base(Path(f), base)}
        if not writable:
            messagebox.showwarning("Keine Zielordner", "Es wurden keine beschreibbaren Zielordner gefunden.")
            return None

        dlg = tk.Toplevel(self)
        dlg.title(title)
        try: self.track_window_geometry(dlg, title)
        except Exception: pass
        dlg.geometry("820x620")
        dlg.transient(self)
        dlg.grab_set()
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        info = ttk.Label(
            dlg,
            text="Bitte Zielordner auswählen. Graue Ordner dienen nur der Struktur; auswählbar sind beschreibbare Ordner.",
        )
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        frame = ttk.Frame(dlg)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=("path",), show="tree")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree.tag_configure("writable", foreground="black")
        tree.tag_configure("context", foreground="#777777")

        nodes: dict[tuple[str, ...], str] = {}
        path_by_iid: dict[str, Path] = {}
        writable_iids: set[str] = set()

        def rel_parts(path: Path) -> tuple[str, ...]:
            try:
                rel = path.relative_to(base)
                if str(rel) == ".":
                    return (base.name or str(base),)
                return tuple(rel.parts)
            except ValueError:
                return tuple(path.parts)

        for folder in sorted(folders, key=lambda p: str(p).lower()):
            parts = rel_parts(folder)
            for i in range(1, len(parts) + 1):
                prefix = parts[:i]
                if prefix in nodes:
                    continue
                parent_prefix = parts[: i - 1]
                parent_iid = nodes.get(parent_prefix, "")
                # Pfad zum Präfix rekonstruieren.
                try:
                    if len(prefix) == 1 and prefix[0] == (base.name or str(base)):
                        prefix_path = base
                    else:
                        prefix_path = base.joinpath(*prefix)
                except Exception:
                    prefix_path = folder
                is_writable = str(prefix_path.resolve()) in writable if prefix_path.exists() else False
                iid = tree.insert(parent_iid, "end", text=prefix[-1], values=(str(prefix_path),), tags=("writable" if is_writable else "context",))
                nodes[prefix] = iid
                path_by_iid[iid] = prefix_path
                if is_writable:
                    writable_iids.add(iid)

        # Aktuellen Ordner markieren, falls möglich.
        current_path = None
        if current_display:
            current_path = self.target_folder_map.get(current_display) or getattr(self, "admin_destination_map", {}).get(current_display)
        if current_path:
            current_resolved = str(Path(current_path).resolve())
            for iid, pth in path_by_iid.items():
                if pth.exists() and str(pth.resolve()) == current_resolved:
                    tree.selection_set(iid)
                    tree.see(iid)
                    break

        selected_path: list[Path | None] = [None]

        def accept() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Keine Auswahl", "Bitte einen Zielordner auswählen.", parent=dlg)
                return
            iid = sel[0]
            path = path_by_iid.get(iid)
            if not path or str(path.resolve()) not in writable:
                tree.item(iid, open=True)
                messagebox.showwarning("Nicht auswählbar", "Dieser Ordner dient nur der Struktur. Bitte einen beschreibbaren Zielordner auswählen.", parent=dlg)
                return
            selected_path[0] = path
            dlg.destroy()

        tree.bind("<Double-1>", lambda _e: accept())
        buttons = ttk.Frame(dlg)
        buttons.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 10))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Ordner übernehmen", command=accept).grid(row=0, column=1, sticky="e", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dlg.destroy).grid(row=0, column=2, sticky="e", padx=4)

        self.wait_window(dlg)
        return selected_path[0]

    def load_writable_folders(self, show_message: bool = True) -> None:
        if getattr(self, "_loading_writable_folders", False):
            return
        self._loading_writable_folders = True
        try:
            base = self.nextcloud_base_path(show_message=show_message)
            if base is None:
                self.writable_folders = []
                self.target_folder_map = {}
                if hasattr(self, "target_combo"):
                    self.target_combo["values"] = []
                if hasattr(self, "target_folder_var"):
                    self.target_folder_var.set("")
                if hasattr(self, "file_view_combo"):
                    self.refresh_file_view_folder_choices()
                return
            self.ensure_standard_metadata_folder()
            self.writable_folders = find_writable_folders(base)
            metadata_folder = self.metadata_folder_path()
            filtered: list[Path] = []
            for folder in self.writable_folders:
                try:
                    if folder == metadata_folder or metadata_folder in folder.parents:
                        continue
                except Exception:
                    pass
                if not self.is_folder_allowed_for_current_user(folder, base):
                    continue
                filtered.append(folder)
            self.writable_folders = filtered
            self.target_folder_map = {self.display_path_for_folder(path, base): path for path in self.writable_folders}
            values = sorted(self.target_folder_map.keys(), key=str.lower)
            if hasattr(self, "target_combo"):
                self.target_combo["values"] = values
            if values and self.target_folder_var.get() not in values:
                self.target_folder_var.set(self.default_upload_target() or values[0])
            elif not values:
                self.target_folder_var.set("")
            if hasattr(self, "file_view_combo"):
                self.refresh_file_view_folder_choices()
            if hasattr(self, "admin_destination_combo"):
                self.refresh_admin_destination_choices()
            self.update_connection_status()
            app_log("info", "Zielordner geprüft", count=len(values), user=self.username_var.get())
            if show_message:
                messagebox.showinfo("Ordnerprüfung", f"{len(values)} beschreibbare Zielordner gefunden.")
        finally:
            self._loading_writable_folders = False

    def filename_keyword_suggestions(self, path: Path) -> list[str]:
        """Leitet einfache Stichwortvorschläge aus dem Dateinamen ab.

        Datum, Ort und Dateiendung werden herausgefiltert. Die Vorschläge werden
        nur als Vorbelegung genutzt und können vom Bearbeiter gelöscht/ergänzt werden.
        """
        stem = path.stem
        norm = self.normalize_folder_token(stem)
        # Technisch sauberer: Dateiname zunächst in Segmente zerlegen.
        raw = stem.replace('-', '_').replace(' ', '_')
        parts = [p for p in re.split(r"[_\s\-]+", raw) if p]
        stop = {"jpg","jpeg","png","pdf","doc","docx","odt","xls","xlsx","tif","tiff","scan","datei"}
        place_tokens = set()
        try:
            place_tokens.add(self.normalize_folder_token(self.meta_vars.get("place").get()))
            place_tokens.add(self.normalize_folder_token(self.place_var.get()))
        except Exception:
            pass
        out=[]; seen=set()
        for part in parts:
            token = self.normalize_folder_token(part)
            if not token or token in seen:
                continue
            if token in stop or token in place_tokens:
                continue
            if re.fullmatch(r"\d{2,8}", token) or token == "0000":
                continue
            if len(token) < 3:
                continue
            seen.add(token)
            out.append(token)
        return out

    def apply_filename_keyword_suggestions(self, path: Path) -> None:
        """Trägt Stichwortvorschläge aus dem Dateinamen ins Stichwortfeld ein."""
        if "keywords" not in self.meta_vars:
            return
        suggestions = self.filename_keyword_suggestions(path)
        if not suggestions:
            return
        current = str(self.meta_vars["keywords"].get() or "").strip()
        current_parts = [p.strip() for p in re.split(r"[,;]", current) if p.strip()]
        seen = {self.normalize_folder_token(p) for p in current_parts}
        for suggestion in suggestions:
            if self.normalize_folder_token(suggestion) not in seen:
                current_parts.append(suggestion)
                seen.add(self.normalize_folder_token(suggestion))
        self.meta_vars["keywords"].set(", ".join(current_parts))

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
                    ):
                        if extra_key in parsed_json_metadata and extra_key not in item:
                            item[extra_key] = parsed_json_metadata.get(extra_key)
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


    def save_pane_positions(self) -> None:
        try:
            if hasattr(self, "viewer_outer_pane"):
                self.config_data["viewer_outer_sash"] = int(self.viewer_outer_pane.sashpos(0))
            if hasattr(self, "viewer_right_pane"):
                self.config_data["viewer_right_sash"] = int(self.viewer_right_pane.sashpos(0))
            if hasattr(self, "admin_outer_pane"):
                self.config_data["admin_outer_sash"] = int(self.admin_outer_pane.sashpos(0))
            if hasattr(self, "admin_right_pane"):
                self.config_data["admin_right_sash"] = int(self.admin_right_pane.sashpos(0))
            save_config(self.config_data)
        except Exception:
            pass

    def restore_pane_positions(self) -> None:
        try:
            if hasattr(self, "viewer_outer_pane") and self.config_data.get("viewer_outer_sash"):
                self.viewer_outer_pane.sashpos(0, int(self.config_data.get("viewer_outer_sash")))
            if hasattr(self, "viewer_right_pane") and self.config_data.get("viewer_right_sash"):
                self.viewer_right_pane.sashpos(0, int(self.config_data.get("viewer_right_sash")))
            if hasattr(self, "admin_outer_pane") and self.config_data.get("admin_outer_sash"):
                self.admin_outer_pane.sashpos(0, int(self.config_data.get("admin_outer_sash")))
            if hasattr(self, "admin_right_pane") and self.config_data.get("admin_right_sash"):
                self.admin_right_pane.sashpos(0, int(self.config_data.get("admin_right_sash")))
        except Exception:
            pass


    def save_tree_column_widths(self, silent: bool = False) -> None:
        widths = self.config_data.setdefault("tree_column_widths", {})
        if hasattr(self, "history_tree"):
            widths["history"] = {col: int(self.history_tree.column(col, "width")) for col in self.history_tree["columns"]}
        save_config(self.config_data)
        if not silent:
            messagebox.showinfo("Ansicht", "Spaltenbreiten wurden gespeichert.")

    # Historie
    def refresh_history(self) -> None:
        if not hasattr(self, "history_tree"):
            return
        scope = getattr(self, "history_scope_var", tk.StringVar(value="all")).get()
        self.config_data["history_scope"] = scope
        save_config(self.config_data)
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.history_upload_id_by_item = {}

        # Primär: Dashboard aus MySQL/API laden.
        if self.api_token:
            try:
                response = self.api.list_documents(self.api_token, only_own=(scope == "own"))
                current_name = (self.display_name_var.get().strip() if hasattr(self, "display_name_var") else "")
                current_user_id = str((self.current_user or {}).get("id", ""))
                for doc in response.get("documents", []):
                    if scope == "own":
                        doc_user_id = str(doc.get("uploaded_by_user_id") or doc.get("user_id") or "")
                        doc_user_name = str(doc.get("uploaded_by_name") or doc.get("uploaded_by") or "")
                        # Server filtert für Ortschronisten bereits, Superadmin/Admin bekommen aber ggf. alles.
                        # Deshalb zusätzlich lokal sauber filtern.
                        if current_user_id and doc_user_id and doc_user_id != current_user_id:
                            continue
                        if not doc_user_id and current_name and doc_user_name and doc_user_name != current_name:
                            continue
                    upload_id = str(doc.get("upload_id", "") or "")
                    time_text = str(doc.get("updated_at") or doc.get("uploaded_at") or doc.get("created_at") or "")
                    user_text = str(doc.get("uploaded_by_name") or doc.get("uploaded_by") or "")
                    action_text = f"Status: {doc.get('status', '')}"
                    details = f"{doc.get('current_filename') or doc.get('original_filename') or ''} | {doc.get('document_type') or ''} | {doc.get('place') or ''}"
                    iid = self.history_tree.insert("", "end", values=(time_text, user_text, action_text, details))
                    self.history_upload_id_by_item[iid] = upload_id
                return
            except ApiError as exc:
                app_log_exception("Logout über API fehlgeschlagen", exc)

        # Fallback: lokale Historie, falls API nicht erreichbar ist.
        current_name = self.display_name_var.get().strip()
        for entry in list_history():
            if scope == "own" and entry.user_display_name != current_name:
                continue
            iid = self.history_tree.insert("", "end", values=(entry.timestamp, entry.user_display_name, entry.action, entry.details))
            self.history_upload_id_by_item[iid] = entry.upload_id

    def show_history_metadata_details(self) -> None:
        if not hasattr(self, "history_tree"):
            return
        sel = self.history_tree.selection()
        if not sel:
            return
        upload_id = getattr(self, "history_upload_id_by_item", {}).get(sel[0])
        details = self.history_tree.item(sel[0], "values")
        item = None
        if upload_id and self.api_token:
            item = self.api_get_document_item(str(upload_id))
        if not item and upload_id:
            for meta in load_metadata_files(self.metadata_folder_path()):
                if str(meta.get("upload_id", "")) == str(upload_id):
                    item = meta
                    break
        text = self.format_metadata_plain({k: v for k, v in item.items() if k != "_metadata_file"}) if item else "Keine passenden Metadaten gefunden.\n\nHistorieneintrag:\n" + " | ".join(str(v) for v in details)
        dialog = tk.Toplevel(self)
        dialog.title("Metadaten zum Historieneintrag")
        try: self.track_window_geometry(dialog, "Metadaten zum Historieneintrag")
        except Exception: pass
        dialog.transient(self)
        dialog.geometry("900x650")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        txt, frame = self.make_scrolled_text(dialog, height=25, wrap="none")
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        ttk.Button(dialog, text="Schließen", command=dialog.destroy).grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))


    # Punkte / Beitragsauswertung
    def _current_points_year(self) -> int:
        return datetime.now().year

    def open_point_rules_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Punkteregeln dürfen nur Superadmins verwalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkteregeln ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkteregeln verwalten")
        try: self.track_window_geometry(dialog, "Punkteregeln verwalten")
        except Exception: pass
        dialog.geometry("1120x600")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        tree = ttk.Treeview(dialog, columns=("key", "label", "category", "points", "active"), show="headings", selectmode="browse")
        for col, label, width in [("key", "Regel", 180), ("label", "Beschreibung", 380), ("category", "Kategorie", 110), ("points", "Punkte", 90), ("active", "Aktiv", 70)]:
            tree.heading(col, text=label, anchor="w", command=lambda c=col: sort_point_rules_tree(c))
            tree.column(col, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        form = ttk.Frame(dialog, padding=8)
        form.grid(row=2, column=0, sticky="ew")
        for value_col in (1, 3):
            form.columnconfigure(value_col, weight=1, uniform="point_rule_fields")
        rule_key_var = tk.StringVar()
        field_var = tk.StringVar()
        label_var = tk.StringVar()
        category_var = tk.StringVar()
        points_var = tk.StringVar()
        active_var = tk.BooleanVar(value=True)
        metadata_fields = [
            ("archive_name", "Archiv / Sammlung"),
            ("archive_signature", "Archivsignatur"),
            ("copyright_author", "Urheber/in"),
            ("description", "Beschreibung"),
            ("document_date", "Datum / Zeitraum"),
            ("event", "Ereignis"),
            ("keywords", "Stichwörter"),
            ("license_note", "Lizenz / Einschränkungen"),
            ("original_location", "Standort Original"),
            ("place", "Ort"),
            ("rights_holder", "Rechteinhaber"),
            ("rights_note", "Rechtehinweis"),
            ("source", "Quelle / Herkunft"),
            ("usage_permission", "Nutzungsfreigabe"),
        ]
        field_labels = [f"{key} - {label}" for key, label in metadata_fields]
        field_by_label = {field_labels[i]: metadata_fields[i][0] for i in range(len(metadata_fields))}
        label_by_field = {key: label for key, label in metadata_fields}
        ttk.Label(form, text="Metadatenfeld:").grid(row=0, column=0, sticky="w", padx=(0,4), pady=3)
        field_combo = ttk.Combobox(form, textvariable=field_var, values=field_labels, state="readonly")
        field_combo.grid(row=0, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Beschreibung:").grid(row=0, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=label_var).grid(row=0, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Kategorie:").grid(row=1, column=0, sticky="w", padx=(0,4), pady=3)
        category_options = ["metadata", "manual"]
        category_combo = ttk.Combobox(form, textvariable=category_var, values=category_options, state="readonly")
        category_combo.grid(row=1, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Punkte:").grid(row=1, column=2, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=points_var).grid(row=1, column=3, sticky="ew", padx=(0,10), pady=3)
        ttk.Label(form, text="Regel:").grid(row=2, column=0, sticky="w", padx=(0,4), pady=3)
        ttk.Entry(form, textvariable=rule_key_var, state="readonly").grid(row=2, column=1, sticky="ew", padx=(0,10), pady=3)
        ttk.Checkbutton(form, text="Aktiv", variable=active_var).grid(row=2, column=3, sticky="w")
        valid_rule_map = {key: {"rule_key": key, "label": label, "category": cat, "meaning": meaning} for key, label, cat, meaning in VALID_POINT_RULES}

        def source_field_from_rule_key(rule_key: str) -> str:
            key = str(rule_key or "").strip()
            for suffix in ("_metadata", "_metadaten", "_manual"):
                if key.endswith(suffix):
                    return key[:-len(suffix)]
            return self.point_rule_source_field_from_key(key)

        def field_label_for_key(field_key: str) -> str:
            return f"{field_key} - {label_by_field.get(field_key, field_key)}"

        def selected_field_key() -> str:
            text = field_var.get().strip()
            return field_by_label.get(text, text.split(" - ", 1)[0].strip())

        def update_rule_from_field_category(*_args):
            field_key = selected_field_key()
            category = category_var.get().strip()
            if field_key and category in {"metadata", "manual"}:
                rule_key_var.set(f"{field_key}_{category}")
                if not label_var.get().strip():
                    label_var.set(f"{label_by_field.get(field_key, field_key)} {'angegeben' if category == 'metadata' else 'manuell ergänzt'}")

        def sort_point_rules_tree(column: str) -> None:
            rows = [(tree.set(iid, column), iid) for iid in tree.get_children("")]
            numeric = column == "points"
            reverse = getattr(tree, "_sort_reverse", {}).get(column, False)
            if numeric:
                rows.sort(key=lambda item: int(float(item[0] or 0)), reverse=reverse)
            else:
                rows.sort(key=lambda item: str(item[0]).lower(), reverse=reverse)
            for index, (_value, iid) in enumerate(rows):
                tree.move(iid, "", index)
            sort_state = dict(getattr(tree, "_sort_reverse", {}))
            sort_state[column] = not reverse
            tree._sort_reverse = sort_state

        def load_rules():
            for item in tree.get_children():
                tree.delete(item)
            try:
                resp = self.api.list_point_rules(self.api_token, int(year_var.get()))
                used_keys = set()
                for rule in resp.get("rules", []):
                    used_keys.add(str(rule.get("rule_key", "")))
                    tree.insert("", "end", values=(rule.get("rule_key", ""), rule.get("label", ""), rule.get("category", ""), rule.get("points", 0), "ja" if int(rule.get("is_active", 1)) else "nein"))
            except Exception as exc:
                messagebox.showerror("Punkteregeln", str(exc))

        def select_rule(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            field_key = source_field_from_rule_key(vals[0])
            field_var.set(field_label_for_key(field_key))
            rule_key_var.set(vals[0]); label_var.set(vals[1]); category_var.set(vals[2]); points_var.set(vals[3]); active_var.set(str(vals[4]).lower() in {"ja", "1", "true"})

        def apply_to_tree():
            update_rule_from_field_category()
            key = rule_key_var.get().strip()
            if key in valid_rule_map and not label_var.get().strip():
                label_var.set(valid_rule_map[key]["label"])
            if not category_var.get().strip():
                category_var.set("metadata")
            vals = (key, label_var.get().strip(), category_var.get().strip(), points_var.get().strip() or "0", "ja" if active_var.get() else "nein")
            if not vals[0] or not vals[1]:
                messagebox.showwarning("Punkteregeln", "Regel und Beschreibung sind erforderlich.")
                return
            try:
                int(float(vals[3]))
            except Exception:
                messagebox.showwarning("Punkteregeln", "Punkte muss eine Zahl sein.")
                return
            sel = tree.selection()
            if sel:
                tree.item(sel[0], values=vals)
            else:
                existing = next((iid for iid in tree.get_children() if str(tree.item(iid, "values")[0]) == key), None)
                if existing:
                    tree.selection_set(existing)
                    tree.item(existing, values=vals)
                else:
                    tree.insert("", "end", values=vals)

        def new_rule():
            tree.selection_remove(tree.selection())
            field_var.set(field_labels[0] if field_labels else "")
            rule_key_var.set("")
            label_var.set("")
            category_var.set("metadata")
            points_var.set("0")
            active_var.set(True)
            update_rule_from_field_category()
            field_combo.focus_set()

        def delete_rule():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Punkteregeln", "Bitte zuerst eine Regel in der Liste auswählen.", parent=dialog)
                return
            vals = tree.item(sel[0], "values")
            key = str(vals[0] or "")
            if not messagebox.askyesno("Punkteregeln", f"Regel '{key}' wirklich löschen?\n\nWirksam wird die Löschung erst mit 'Speichern'.", parent=dialog):
                return
            tree.delete(sel[0])
            rule_key_var.set("")
            label_var.set("")
            points_var.set("")
            active_var.set(True)

        def save_rules():
            rules = []
            for iid in tree.get_children():
                key, label, cat, points, active = tree.item(iid, "values")
                rules.append({"rule_key": key, "label": label, "category": cat, "points": int(float(points or 0)), "is_active": str(active).lower() in {"ja", "1", "true"}})
            try:
                self.api.update_point_rules(self.api_token, int(year_var.get()), rules)
                messagebox.showinfo("Punkteregeln", "Punkteregeln wurden gespeichert.")
                load_rules()
            except Exception as exc:
                messagebox.showerror("Punkteregeln", str(exc))

        field_combo.bind("<<ComboboxSelected>>", update_rule_from_field_category)
        category_combo.bind("<<ComboboxSelected>>", update_rule_from_field_category)
        tree.bind("<<TreeviewSelect>>", select_rule)
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(top, text="Laden", command=load_rules).pack(side="left", padx=6)
        ttk.Button(buttons, text="Regel übernehmen", command=apply_to_tree).pack(side="left")
        ttk.Button(buttons, text="Neue Regel", command=new_rule).pack(side="left", padx=6)
        ttk.Button(buttons, text="Regel löschen", command=delete_rule).pack(side="left")
        ttk.Button(buttons, text="Speichern", command=save_rules).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_rules()

    def open_my_points_dialog(self) -> None:
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für den Punktestand ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Mein Punktestand")
        try: self.track_window_geometry(dialog, "Mein Punktestand")
        except Exception: pass
        dialog.geometry("1040x660")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        selected_user_var = tk.StringVar()
        user_map: dict[str, int] = {}
        if self.is_current_admin():
            ttk.Label(top, text="Bearbeiter:").pack(side="left", padx=(16, 4))
            labels, users = self.load_active_user_options()
            for lbl, u in users.items():
                try:
                    user_map[lbl] = int(u.get("id") or 0)
                except Exception:
                    pass
            own_id = self.current_user_id()
            default_label = next((lbl for lbl, uid in user_map.items() if uid == own_id), (labels[0] if labels else ""))
            selected_user_var.set(default_label)
            user_combo = ttk.Combobox(top, textvariable=selected_user_var, values=labels, state="readonly", width=34)
            user_combo.pack(side="left", padx=4)

        summary_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=summary_var, font=("", 11, "bold"), padding=8).grid(row=1, column=0, sticky="w")

        tree = ttk.Treeview(dialog, columns=("date", "document", "category", "reason", "points", "status", "credit"), show="headings")
        for col, label, width in [("date", "Datum", 140), ("document", "Dokument", 260), ("category", "Kategorie", 120), ("reason", "Grund", 310), ("points", "Punkte", 70), ("status", "Dokumentstatus", 110), ("credit", "Wertung", 110)]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=2, column=1, sticky="ns")
        row_upload_ids: dict[str, str] = {}

        def load_my_points():
            for iid in tree.get_children():
                tree.delete(iid)
            row_upload_ids.clear()
            try:
                user_id = user_map.get(selected_user_var.get()) if self.is_current_admin() else None
                resp = self.api.my_points(self.api_token, int(year_var.get()), user_id=user_id)
                own = resp.get("own", {}) or {}
                rank = resp.get("rank")
                participant_count = resp.get("participant_count")
                total = own.get("total_points", 0)
                provisional = own.get("provisional_points", 0)
                summary_var.set(
                    f"{total} gewertete Punkte · {provisional} vorläufig · Rang {rank or '-'} von {participant_count or 0} · "
                    f"Metadaten {own.get('metadata_points', 0)} · Rechte/Sonder {own.get('manual_points', 0)} · "
                    f"Personen {own.get('persons_points', 0)} · Admin {own.get('admin_points', 0)}"
                )
                for idx, row in enumerate(resp.get("events", []) or []):
                    status = row.get("document_status", "")
                    credit = "gewertet" if status == "uebernommen" or int(row.get("is_manual", 0) or 0) == 1 else "vorläufig"
                    iid = f"row{idx}"
                    tree.insert("", "end", iid=iid, values=(row.get("created_at", ""), row.get("filename", row.get("upload_id", "")), row.get("category", ""), row.get("reason", ""), row.get("points", 0), status, credit))
                    row_upload_ids[iid] = str(row.get("upload_id") or "")
            except Exception as exc:
                messagebox.showerror("Mein Punktestand", str(exc), parent=dialog)

        def open_selected_from_points(_event=None):
            sel = tree.selection()
            if not sel:
                return
            upload_id = row_upload_ids.get(sel[0], "")
            dialog.destroy()
            self.open_document_in_admin_by_upload_id(upload_id)

        tree.bind("<Double-1>", open_selected_from_points)
        if self.is_current_admin():
            try:
                user_combo.bind("<<ComboboxSelected>>", lambda _e: load_my_points())
            except Exception:
                pass
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(top, text="Aktualisieren", command=load_my_points).pack(side="left", padx=6)
        ttk.Label(buttons, text="Doppelklick öffnet das Dokument in 'Dateien bearbeiten'.", foreground="#555555").pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_my_points()

    def open_points_summary_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Auswertungen sind Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für die Auswertung ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Beitragsauswertung")
        try: self.track_window_geometry(dialog, "Beitragsauswertung")
        except Exception: pass
        dialog.geometry("920x560")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        tree = ttk.Treeview(dialog, columns=("user", "place", "upload", "metadata", "persons", "admin", "manual", "total"), show="headings")
        for col, label, width in [("user", "Benutzer", 220), ("place", "Ort", 120), ("upload", "Upload", 70), ("metadata", "Metadaten", 90), ("persons", "Personen", 80), ("admin", "Admin", 70), ("manual", "Sonder", 70), ("total", "Gesamt", 80)]:
            tree.heading(col, text=label, anchor="w")
            tree.column(col, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        rows_cache = []
        def load_summary():
            nonlocal rows_cache
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.points_summary(self.api_token, int(year_var.get()))
                rows_cache = resp.get("summary", []) or []
                for row in rows_cache:
                    tree.insert("", "end", values=(row.get("user_display_name", ""), row.get("place", ""), row.get("upload_points", 0), row.get("metadata_points", 0), row.get("persons_points", 0), row.get("admin_points", 0), row.get("manual_points", 0), row.get("total_points", 0)))
            except Exception as exc:
                messagebox.showerror("Beitragsauswertung", str(exc))
        def export_csv():
            if not rows_cache:
                messagebox.showinfo("Export", "Keine Daten zum Export vorhanden.")
                return
            path = filedialog.asksaveasfilename(title="CSV exportieren", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Benutzer", "Ort", "Upload", "Metadaten", "Personen", "Admin", "Sonder", "Gesamt"])
                for row in rows_cache:
                    writer.writerow([row.get("user_display_name", ""), row.get("place", ""), row.get("upload_points", 0), row.get("metadata_points", 0), row.get("persons_points", 0), row.get("admin_points", 0), row.get("manual_points", 0), row.get("total_points", 0)])
            messagebox.showinfo("Export", f"CSV wurde gespeichert:\n{path}")
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(top, text="Aktualisieren", command=load_summary).pack(side="left", padx=6)
        ttk.Button(buttons, text="CSV exportieren", command=export_csv).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load_summary()

    def open_manual_points_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Sonderpunkte sind Admins vorbehalten.")
            return
        item = None
        try:
            item = self.selected_admin_upload()
        except Exception:
            item = None
        if not item or not item.get("upload_id"):
            messagebox.showwarning("Sonderpunkte", "Bitte im Reiter 'Dateien bearbeiten' zuerst ein Dokument auswählen.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Sonderpunkte ist eine API-Anmeldung erforderlich.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Sonderpunkte vergeben")
        try: self.track_window_geometry(dialog, "Sonderpunkte vergeben")
        except Exception: pass
        dialog.geometry("760x430")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(5, weight=1)
        ttk.Label(dialog, text=f"Dokument: {item.get('current_filename') or item.get('original_filename')}").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))

        users_resp = self.api.list_users(self.api_token)
        users = users_resp.get("users", []) or []
        user_map = {f"{u.get('display_name')} ({u.get('username')})": int(u.get('id')) for u in users if int(u.get('is_active', 1)) == 1}
        user_var = tk.StringVar(value=next(iter(user_map.keys()), ""))

        bonus_rules = []
        try:
            rules_resp = self.api.list_point_rules(self.api_token, self._current_points_year())
            for rule in rules_resp.get("rules", []) or []:
                if str(rule.get("category", "")).strip() in {"manual", "manual_bonus"} and int(rule.get("is_active", 1)) == 1:
                    bonus_rules.append(rule)
        except Exception:
            bonus_rules = []
        if not bonus_rules:
            bonus_rules = [
                {"rule_key": key, "label": label, "points": points, "category": "manual_bonus"}
                for key, label, points in DEFAULT_MANUAL_BONUS_RULES
            ]
        bonus_labels = [f"{r.get('label', r.get('rule_key'))} ({int(r.get('points', 0))} Punkte)" for r in bonus_rules]
        bonus_map = {bonus_labels[i]: bonus_rules[i] for i in range(len(bonus_rules))}
        bonus_var = tk.StringVar(value=bonus_labels[0] if bonus_labels else "")
        points_var = tk.StringVar(value=str(int(bonus_rules[0].get("points", 0))) if bonus_rules else "0")
        reason_text = tk.Text(dialog, height=8, wrap="word")

        ttk.Label(dialog, text="Empfänger:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ttk.Combobox(dialog, textvariable=user_var, values=list(user_map.keys()), state="readonly").grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Leistungsart:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        bonus_combo = ttk.Combobox(dialog, textvariable=bonus_var, values=bonus_labels, state="readonly")
        bonus_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Punkte:").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(dialog, textvariable=points_var, width=8).grid(row=3, column=1, sticky="w", padx=10, pady=4)
        ttk.Label(dialog, text="Begründung:").grid(row=4, column=0, sticky="nw", padx=10, pady=4)
        reason_text.grid(row=4, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Hinweis: Manuell vergebene Punkte müssen begründet werden. Bei 'Besondere Zuarbeit' bitte Punkte bewusst festlegen.", foreground="#555555").grid(row=5, column=1, sticky="w", padx=10, pady=(0, 4))

        def on_bonus_selected(_event=None):
            rule = bonus_map.get(bonus_var.get())
            if rule:
                points_var.set(str(int(rule.get("points", 0))))
                if not reason_text.get("1.0", "end").strip():
                    reason_text.insert("1.0", str(rule.get("label", "")))
        bonus_combo.bind("<<ComboboxSelected>>", on_bonus_selected)
        on_bonus_selected()

        def save_manual():
            try:
                user_id = user_map.get(user_var.get())
                if not user_id:
                    raise ValueError("Bitte einen Benutzer auswählen.")
                reason = reason_text.get("1.0", "end").strip()
                if not reason:
                    raise ValueError("Bitte eine Begründung erfassen.")
                points = int(points_var.get())
                if points == 0:
                    raise ValueError("Bitte eine Punktzahl ungleich 0 erfassen.")
                rule = bonus_map.get(bonus_var.get()) or {}
                category = str(rule.get("category") or "manual_bonus")
                rule_key = str(rule.get("rule_key") or "")
                source_field = self.point_rule_source_field_from_key(rule_key)
                label = str(rule.get("label") or "Sonderpunkte")
                full_reason = f"{label}: {reason}" if not reason.startswith(label) else reason
                self.api.add_manual_points(self.api_token, str(item.get("upload_id")), user_id, points, full_reason, category, rule_key=rule_key, source_field=source_field)
                self.update_admin_document_points_display(str(item.get("upload_id", "")))
                messagebox.showinfo("Sonderpunkte", "Sonderpunkte wurden gespeichert.")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc))

        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save_manual).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right")


    def open_points_settings_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Punkte-Einstellungen dürfen nur Superadmins ändern.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für Punkte-Einstellungen ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Punkte-Einstellungen")
        try: self.track_window_geometry(dialog, "Punkte-Einstellungen")
        except Exception: pass
        dialog.geometry("520x180")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        points_per_hour_var = tk.StringVar(value="150")
        try:
            resp = self.api.get_manual_points_settings(self.api_token)
            points_per_hour_var.set(str(resp.get("points_per_hour", 150)))
        except Exception:
            points_per_hour_var.set("150")
        ttk.Label(dialog, text="Standardpunkte pro Stunde für manuelle Sonderpunkte:").grid(row=0, column=0, sticky="w", padx=10, pady=(14, 6))
        ttk.Entry(dialog, textvariable=points_per_hour_var, width=10).grid(row=0, column=1, sticky="w", padx=10, pady=(14, 6))
        ttk.Label(dialog, text="Wird ein Zeitaufwand erfasst, berechnet ODV daraus einen Punktvorschlag.\nDie Punkte bleiben vor dem Speichern manuell änderbar.", foreground="#555555").grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=6)
        def save():
            try:
                val = int(float(points_per_hour_var.get().replace(",", ".")))
                if val <= 0:
                    raise ValueError("Bitte einen positiven Wert erfassen.")
                self.api.save_manual_points_settings(self.api_token, val)
                messagebox.showinfo("Punkte-Einstellungen", "Einstellungen wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Punkte-Einstellungen", str(exc), parent=dialog)
        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

    def point_rule_source_field_from_key(self, rule_key: str) -> str:
        key = str(rule_key or "").strip()
        for suffix in ("_metadata", "_metadaten", "_manual"):
            if key.endswith(suffix):
                key = key[:-len(suffix)]
                break
        aliases = {
            "metadata_description": "description",
            "metadata_keywords": "keywords",
            "metadata_source": "source",
            "rights_author": "copyright_author",
            "rights_usage_permission": "usage_permission",
            "event_topic": "event",
            "openai_metadata": "openai_metadata",
        }
        return aliases.get(key, key or "manual_bonus")

    def _manual_rule_options(self, year: int) -> tuple[list[str], dict[str, dict]]:
        rules = []
        try:
            resp = self.api.list_point_rules(self.api_token, int(year))
            for rule in resp.get("rules", []) or []:
                if str(rule.get("category", "")).strip() == "manual" and int(rule.get("is_active", 1)) == 1:
                    rules.append(rule)
        except Exception:
            rules = []
        if not rules:
            rules = [{"rule_key": key, "label": label, "points": points, "category": "manual"} for key, label, points in DEFAULT_MANUAL_BONUS_RULES]
        labels = [f"{r.get('label', r.get('rule_key'))} [{r.get('rule_key')}]" for r in rules]
        return labels, {labels[i]: rules[i] for i in range(len(rules))}

    def open_manual_special_points_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Manuelle Sonderpunkte sind Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für manuelle Sonderpunkte ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Sonderpunkte für Ortschronisten")
        try: self.track_window_geometry(dialog, "Sonderpunkte für Ortschronisten")
        except Exception: pass
        dialog.geometry("860x560")
        dialog.transient(self)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(6, weight=1)

        users_resp = self.api.list_users(self.api_token)
        users = users_resp.get("users", []) or []
        user_map = {f"{u.get('display_name')} ({u.get('username')})": int(u.get('id')) for u in users if int(u.get('is_active', 1)) == 1}
        user_var = tk.StringVar(value=next(iter(user_map.keys()), ""))
        year = self._current_points_year()
        rule_labels, rule_map = self._manual_rule_options(year)
        rule_var = tk.StringVar(value=rule_labels[0] if rule_labels else "")
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        hours_var = tk.StringVar()
        points_var = tk.StringVar()
        pph_var = tk.StringVar(value="150")
        try:
            settings = self.api.get_manual_points_settings(self.api_token)
            pph_var.set(str(settings.get("points_per_hour", 150)))
        except Exception:
            pass
        reason_text = tk.Text(dialog, height=6, wrap="word")
        note_text = tk.Text(dialog, height=4, wrap="word")

        ttk.Label(dialog, text="Ortschronist:").grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        ttk.Combobox(dialog, textvariable=user_var, values=list(user_map.keys()), state="readonly").grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 4))
        ttk.Label(dialog, text="Tätigkeit / Regel:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        rule_combo = ttk.Combobox(dialog, textvariable=rule_var, values=rule_labels, state="readonly")
        rule_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(dialog, text="Datum der Tätigkeit:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(dialog, textvariable=date_var, width=14).grid(row=2, column=1, sticky="w", padx=10, pady=4)
        row3 = ttk.Frame(dialog)
        row3.grid(row=3, column=1, sticky="w", padx=10, pady=4)
        ttk.Label(dialog, text="Zeitaufwand / Punkte:").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(row3, textvariable=hours_var, width=10).pack(side="left")
        ttk.Label(row3, text=" Stunden × ").pack(side="left")
        ttk.Entry(row3, textvariable=pph_var, width=7).pack(side="left")
        ttk.Label(row3, text=" Punkte/Stunde = ").pack(side="left")
        ttk.Entry(row3, textvariable=points_var, width=9).pack(side="left")
        ttk.Label(dialog, text="Beschreibung / Begründung:").grid(row=4, column=0, sticky="nw", padx=10, pady=4)
        reason_text.grid(row=4, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Bemerkung / Beleg:").grid(row=5, column=0, sticky="nw", padx=10, pady=4)
        note_text.grid(row=5, column=1, sticky="nsew", padx=10, pady=4)
        ttk.Label(dialog, text="Wenn ein Zeitaufwand eingetragen ist, berechnet ODV automatisch einen Vorschlag. Punkte können vor dem Speichern geändert werden.", foreground="#555555").grid(row=6, column=1, sticky="w", padx=10, pady=(0, 4))

        def recalc_points(*_):
            try:
                htxt = hours_var.get().strip().replace(",", ".")
                if not htxt:
                    rule = rule_map.get(rule_var.get()) or {}
                    default_points = int(rule.get("points", 0) or 0)
                    if default_points and not points_var.get().strip():
                        points_var.set(str(default_points))
                    return
                hours = float(htxt)
                pph = int(float(pph_var.get().strip().replace(",", ".") or "150"))
                points_var.set(str(int(round(hours * pph))))
            except Exception:
                pass
        hours_var.trace_add("write", recalc_points)
        pph_var.trace_add("write", recalc_points)
        rule_combo.bind("<<ComboboxSelected>>", lambda e: recalc_points())
        recalc_points()

        def save():
            try:
                uid = user_map.get(user_var.get())
                if not uid:
                    raise ValueError("Bitte einen Benutzer auswählen.")
                rule = rule_map.get(rule_var.get()) or {}
                rule_key = str(rule.get("rule_key") or "manual_other")
                reason = reason_text.get("1.0", "end").strip()
                note = note_text.get("1.0", "end").strip()
                if not reason:
                    raise ValueError("Bitte eine Beschreibung/Begründung erfassen.")
                points = int(float(points_var.get().strip().replace(",", ".")))
                if points == 0:
                    raise ValueError("Bitte Punkte ungleich 0 erfassen.")
                hours = None
                if hours_var.get().strip():
                    hours = float(hours_var.get().strip().replace(",", "."))
                self.api.add_manual_special_points(self.api_token, uid, rule_key, points, reason, activity_date=date_var.get().strip(), hours=hours, note=note)
                messagebox.showinfo("Sonderpunkte", "Manuelle Sonderpunkte wurden gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog, padding=10)
        buttons.grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Speichern", command=save).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")

    def open_manual_special_points_overview_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Keine Berechtigung", "Diese Übersicht ist Admins vorbehalten.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für diese Übersicht ist eine API-Anmeldung erforderlich.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Übersicht manuelle Sonderpunkte")
        try: self.track_window_geometry(dialog, "Übersicht manuelle Sonderpunkte")
        except Exception: pass
        dialog.geometry("1200x680")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        top = ttk.Frame(dialog, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Kalenderjahr:").pack(side="left")
        year_var = tk.StringVar(value=str(self._current_points_year()))
        ttk.Entry(top, textvariable=year_var, width=8).pack(side="left", padx=6)
        cols = ("date", "user", "place", "rule", "hours", "points", "reason", "created_by", "created_at")
        tree = ttk.Treeview(dialog, columns=cols, show="headings")
        widths = {"date":110, "user":190, "place":120, "rule":240, "hours":90, "points":80, "reason":340, "created_by":180, "created_at":150}
        labels = {"date":"Datum", "user":"Ortschronist", "place":"Ort", "rule":"Tätigkeit", "hours":"Stunden", "points":"Punkte", "reason":"Begründung", "created_by":"Vergeben von", "created_at":"Erfasst am"}
        for c in cols:
            tree.heading(c, text=labels[c], anchor="w")
            tree.column(c, width=widths[c], anchor="w", stretch=True)
        tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(dialog, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew", padx=8)
        def load():
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                resp = self.api.list_manual_special_points(self.api_token, int(year_var.get()))
                for row in resp.get("items", []) or []:
                    tree.insert("", "end", values=(row.get("activity_date", ""), row.get("user_display_name", ""), row.get("place", ""), row.get("rule_label", row.get("rule_key", "")), row.get("hours", ""), row.get("points", 0), row.get("reason", ""), row.get("created_by_name", ""), row.get("created_at", "")))
            except Exception as exc:
                messagebox.showerror("Sonderpunkte", str(exc), parent=dialog)
        buttons = ttk.Frame(dialog, padding=8)
        buttons.grid(row=3, column=0, sticky="ew")
        ttk.Button(top, text="Aktualisieren", command=load).pack(side="left", padx=8)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        load()

    def mark_history_seen(self) -> None:
        self.config_data["last_seen_history_at"] = datetime.now().isoformat(timespec="seconds")
        save_config(self.config_data)
        messagebox.showinfo("Historie", "Historie wurde als gesehen markiert. Im MVP bleibt die Tabelle trotzdem sichtbar.")


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
