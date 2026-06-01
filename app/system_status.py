from __future__ import annotations

import getpass
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .config import APP_DIR
from .app_logging import app_log_exception


class SystemStatusMixin:
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
            name = self.display_name_var.get().strip() or "unbekannt"
            role = self.current_role()
            place = self.place_var.get().strip() or "-"
            lines.append(f"Angemeldet: {name} ({role})")
            lines.append(f"Ort: {place}")
        except Exception:
            pass
        try:
            lines.append(f"Windows-Benutzer: {getpass.getuser()}")
        except Exception:
            pass
        try:
            lines.append(f"API-URL: {self.api.base_url or '-'}")
        except Exception:
            pass
        try:
            base = self.base_folder_var.get().strip() or "-"
            lines.append(f"Nextcloud-Stammordner: {base}")
        except Exception:
            pass
        try:
            meta = self.metadata_folder_path()
            lines.append(f"Metadatenordner: {meta}")
        except Exception:
            pass
        try:
            update = self.get_app_update_info()
            latest = str(update.get("version") or "").strip()
            if latest:
                required = "ja" if bool(update.get("required")) else "nein"
                file_name = str(update.get("file_name") or update.get("file") or "").strip()
                lines.append(f"ODV-Updatefreigabe: {latest} (Pflicht: {required}{', Datei: ' + file_name if file_name else ''})")
            else:
                lines.append("ODV-Updatefreigabe: keine")
        except Exception as exc:
            lines.append(f"ODV-Updatefreigabe: nicht prüfbar ({exc})")
        try:
            status = self.api.status()
            api_version = str(status.get("api_version") or status.get("version") or "?")
            lines.append(f"API erreichbar: ja ({api_version})")
            if api_version != "?" and api_version != self.APP_VERSION:
                lines.append(f"Server-Version passend: nein – App {self.APP_VERSION}, API {api_version}")
            else:
                lines.append("Server-Version passend: ja")
        except Exception as exc:
            lines.append(f"API erreichbar: nein ({exc})")
        try:
            migrations = self.api.pending_migrations(self.api_token)
            pending = int(migrations.get("pending_count") or 0)
            lines.append(f"Datenbankmigrationen offen: {pending}")
        except Exception as exc:
            lines.append(f"Datenbankmigrationen: nicht prüfbar ({exc})")
        try:
            missing = self.check_missing_place_folders()
            lines.append(f"Ortsordner-Prüfung: {'nein' if missing else 'ja'}")
            if missing:
                lines.append(f"Fehlende Ortsordner: {len(missing)}")
                for place, folder, full in missing[:10]:
                    lines.append(f"- {place}: {full}")
                if len(missing) > 10:
                    lines.append(f"... weitere fehlende Ortsordner: {len(missing)-10}")
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
            if api_version != "?" and api_version != self.APP_VERSION:
                warnings.append(
                    f"Server-routes.php ist vermutlich nicht aktuell: App {self.APP_VERSION}, API {api_version}.\n"
                    "Bitte routes.php sichern/hochladen, damit App und API wieder zusammenpassen."
                )
        except Exception as exc:
            warnings.append(f"API-Status konnte nicht geprüft werden: {exc}")
        try:
            migrations = self.api.pending_migrations(self.api_token)
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
            try:
                self.track_window_geometry(dialog, "ODV-Systemstatus")
            except Exception:
                pass
            dialog.transient(self)
            dialog.resizable(True, True)
            dialog.columnconfigure(0, weight=1)
            dialog.rowconfigure(0, weight=1)
            frame = ttk.Frame(dialog, padding=14)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            ttk.Label(frame, text="Systemstatus", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
            text = tk.Text(frame, width=92, height=min(18, max(8, len(lines) + 1)), wrap="word")
            text.grid(row=1, column=0, sticky="nsew")
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")
            buttons = ttk.Frame(frame)
            buttons.grid(row=2, column=0, sticky="e", pady=(8, 0))
            ttk.Button(buttons, text="Aktualisieren", command=lambda: self.refresh_system_status_text(text)).pack(side="left", padx=4)
            if self.is_current_admin():
                ttk.Button(buttons, text="Logs öffnen", command=self.open_log_folder).pack(side="left", padx=4)
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

    def open_log_folder(self) -> None:
        try:
            log_dir = APP_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(log_dir))
        except Exception as exc:
            app_log_exception("Logdateien konnten nicht geöffnet werden", exc)
