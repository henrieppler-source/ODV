from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .app_logging import app_log, app_log_exception
from .database import add_history
from .file_service import unique_path_with_counter
from .models import HistoryEntry


class FileAccessManagerMixin:
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
            app_log_exception("Datei konnte nicht kopiert werden", exc, path=str(path))
            messagebox.showerror("Download", f"Datei konnte nicht kopiert werden:\n{exc}")

    def open_document_access_log_dialog(self) -> None:
        if not self.require_admin():
            return
        if not self.api_token:
            messagebox.showwarning("Dokumentzugriffe", "Keine API-Anmeldung vorhanden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Dokumentzugriffe")
        try:
            self.track_window_geometry(dialog, "Dokumentzugriffe")
        except Exception:
            pass
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
