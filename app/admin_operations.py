from __future__ import annotations

import ftplib
import posixpath
import re
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from .api_client import ApiError
from .secure_store import unprotect_text


class AdminOperationsMixin:
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

    def discover_routes_deploy_files(self) -> list[Path]:
        """Findet routes.php plus mögliche Modul-Dateien im selben Ordner."""
        main_path = self.resolve_local_routes_path()
        if not main_path.parent.exists():
            return [main_path]
        files: list[Path] = []
        seen: set[str] = set()
        for candidate in [main_path, *sorted(main_path.parent.glob("routes*.php"))]:
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate
            key = str(resolved).lower()
            if key in seen:
                continue
            if candidate.is_file():
                files.append(candidate)
                seen.add(key)
        return files or [main_path]

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
        local_files = self.discover_routes_deploy_files()
        main_path = self.resolve_local_routes_path()
        if not host or not user or not remote_path:
            raise RuntimeError("FTP-Server, Benutzer oder Zielpfad fehlen in den Admin-Einstellungen.")
        if not password:
            raise RuntimeError("FTP-Passwort ist noch nicht gespeichert. Bitte einmal in den Admin-Einstellungen erfassen.")
        remote_dir = posixpath.dirname(remote_path)
        remote_main_name = posixpath.basename(remote_path)
        if not remote_dir or not remote_main_name:
            raise RuntimeError("FTP-Zielpfad ist ungültig.")
        for local_path in local_files:
            if not local_path.exists():
                raise RuntimeError(f"Lokale Datei nicht gefunden: {local_path}")
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with ftplib.FTP() as ftp:
            ftp.connect(host, port, timeout=30)
            ftp.login(user, password)
            ftp.cwd(remote_dir)
            existing = set(ftp.nlst())
            uploaded = []
            backups_created = []
            sizes: dict[str, int | None] = {}
            for local_path in local_files:
                remote_name = local_path.name if local_path.name != main_path.name else remote_main_name
                stem, ext = posixpath.splitext(remote_name)
                backup_name = f"{stem}_backup_{self.app_version()}_{stamp}{ext or '.php'}"
                if remote_name in existing:
                    ftp.rename(remote_name, backup_name)
                    backups_created.append(backup_name)
                with local_path.open("rb") as fh:
                    ftp.storbinary(f"STOR {remote_name}", fh)
                try:
                    sizes[remote_name] = int(ftp.size(remote_name) or 0)
                except Exception:
                    sizes[remote_name] = None
                uploaded.append({"local_path": str(local_path), "remote_name": remote_name})
        cleanup_deleted = self.cleanup_old_routes_backups_via_ftp(keep=3)
        return {
            "host": host,
            "remote_dir": remote_dir,
            "remote_name": remote_main_name,
            "uploaded": uploaded,
            "backup_names": backups_created,
            "local_path": str(main_path),
            "size": sizes.get(remote_main_name),
            "cleanup_deleted": cleanup_deleted,
        }

    def ftp_connection_info(self) -> tuple[str, int, str, str, str, str]:
        host = str(self.config_data.get("ftp_host", "") or "").strip()
        port = int(str(self.config_data.get("ftp_port", "21") or "21").strip())
        user = str(self.config_data.get("ftp_user", "") or "").strip()
        password = self.stored_ftp_password()
        remote_path = str(self.config_data.get("ftp_remote_routes_path", "") or "").strip()
        remote_dir = posixpath.dirname(remote_path)
        remote_name = posixpath.basename(remote_path)
        if not host or not user or not password or not remote_dir or not remote_name:
            raise RuntimeError("FTP-Zugang oder Zielpfad ist unvollständig.")
        return host, port, user, password, remote_dir, remote_name

    @staticmethod
    def _is_routes_backup_name(name: str) -> bool:
        safe_name = posixpath.basename(str(name))
        return bool(re.match(r"^routes.*_backup_.+\.php$", safe_name, re.IGNORECASE))

    def list_routes_backups_via_ftp(self) -> list[dict]:
        host, port, user, password, remote_dir, _remote_name = self.ftp_connection_info()
        backups: list[dict] = []
        with ftplib.FTP() as ftp:
            ftp.connect(host, port, timeout=30)
            ftp.login(user, password)
            ftp.cwd(remote_dir)
            for name in ftp.nlst():
                if not self._is_routes_backup_name(name):
                    continue
                size = 0
                modified = ""
                try:
                    size = int(ftp.size(name) or 0)
                except Exception:
                    pass
                try:
                    raw = ftp.sendcmd(f"MDTM {name}").split()[-1]
                    modified = datetime.strptime(raw, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    modified = ""
                backups.append({"name": name, "size": size, "modified": modified})
        backups.sort(key=lambda item: (str(item.get("modified") or ""), str(item.get("name") or "")), reverse=True)
        return backups

    def delete_routes_backups_via_ftp(self, names: list[str]) -> int:
        host, port, user, password, remote_dir, _remote_name = self.ftp_connection_info()
        deleted = 0
        with ftplib.FTP() as ftp:
            ftp.connect(host, port, timeout=30)
            ftp.login(user, password)
            ftp.cwd(remote_dir)
            for name in names:
                safe_name = posixpath.basename(str(name))
                if not self._is_routes_backup_name(safe_name):
                    continue
                ftp.delete(safe_name)
                deleted += 1
        return deleted

    def cleanup_old_routes_backups_via_ftp(self, keep: int = 3) -> int:
        backups = self.list_routes_backups_via_ftp()
        grouped: dict[str, list[str]] = {}
        for item in backups:
            name = str(item.get("name") or "")
            if "_backup_" not in name:
                continue
            base_name = name.split("_backup_", 1)[0]
            grouped.setdefault(base_name, []).append(name)
        old_names: list[str] = []
        for names in grouped.values():
            names_sorted = sorted(
                names,
                key=lambda n: next((str(item.get("modified") or "") for item in backups if str(item.get("name") or "") == n), ""),
                reverse=True,
            )
            old_names.extend(names_sorted[max(0, keep):])
        return self.delete_routes_backups_via_ftp([name for name in old_names if name])

    @staticmethod
    def format_backup_size(size: object) -> str:
        try:
            value = int(size)
        except Exception:
            return "n.v."
        if value <= 0:
            return "n.v."
        units = ["B", "KB", "MB", "GB"]
        num = float(value)
        unit = "B"
        for candidate in units:
            unit = candidate
            if num < 1024 or candidate == units[-1]:
                break
            num /= 1024.0
        if unit == "B":
            return f"{value} B"
        return f"{num:.1f} {unit}"

    def open_routes_deploy_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Server-routes.php sichern/hochladen")
        try: self.track_window_geometry(dialog, "Server-routes.php sichern/hochladen")
        except Exception: pass
        dialog.geometry("860x560")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(3, weight=1)

        local_path = self.resolve_local_routes_path()
        remote_path = str(self.config_data.get("ftp_remote_routes_path", "") or "")
        server = str(self.config_data.get("ftp_host", "") or "")
        user = str(self.config_data.get("ftp_user", "") or "")
        port = str(self.config_data.get("ftp_port", "21") or "21")
        password_saved = bool(str(self.config_data.get("ftp_password_dpapi", "") or "").strip())

        text = (
            "ODV sichert die vorhandenen routes*.php-Dateien auf dem Webserver, lädt danach die lokalen Server-Dateien hoch und behält automatisch nur die letzten 3 Server-Backups je Datei.\n\n"
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

        backup_frame = ttk.LabelFrame(dialog, text="Server-Backups", padding=8)
        backup_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        backup_frame.columnconfigure(0, weight=1)
        backup_frame.rowconfigure(0, weight=1)
        backup_tree = ttk.Treeview(backup_frame, columns=("name", "modified", "size"), show="headings", selectmode="extended", height=7)
        for col, label, width in [("name", "Datei", 430), ("modified", "Geändert", 150), ("size", "Größe", 90)]:
            backup_tree.heading(col, text=label, anchor="w")
            backup_tree.column(col, width=width, anchor="w")
        backup_tree.grid(row=0, column=0, sticky="nsew")
        backup_scroll = ttk.Scrollbar(backup_frame, orient="vertical", command=backup_tree.yview)
        backup_tree.configure(yscrollcommand=backup_scroll.set)
        backup_scroll.grid(row=0, column=1, sticky="ns")

        def load_server_backups() -> None:
            for iid in backup_tree.get_children():
                backup_tree.delete(iid)
            try:
                backups = self.list_routes_backups_via_ftp()
                for item in backups:
                    name = str(item.get("name") or "")
                    backup_tree.insert("", "end", iid=name, values=(name, item.get("modified", ""), self.format_backup_size(item.get("size"))))
                result_var.set(f"{len(backups)} Server-Backup(s) gefunden.")
            except Exception as exc:
                result_var.set(f"Server-Backups konnten nicht geladen werden: {exc}")

        def run_deploy() -> None:
            if not messagebox.askyesno(
                "routes.php hochladen",
                "Jetzt die Server-routes.php und alle lokalen routes*.php-Dateien sichern und hochladen?",
                parent=dialog,
            ):
                return
            result_var.set("Upload läuft ...")
            for child in buttons.winfo_children():
                child.configure(state="disabled")

            def worker() -> None:
                try:
                    info = self.deploy_routes_via_ftp()
                    uploaded = info.get("uploaded") or []
                    backup_names = info.get("backup_names") or []
                    lines = [
                        "Upload abgeschlossen.",
                        f"Lokale Hauptdatei: {info.get('local_path')}",
                        f"Serverziel: {info.get('remote_dir')}/{info.get('remote_name')}",
                        f"Größe: {info.get('size') if info.get('size') is not None else 'n.v.'}",
                    ]
                    if uploaded:
                        lines.append("Hochgeladene Dateien:")
                        for item in uploaded:
                            lines.append(f" - {item.get('remote_name')}")
                    if backup_names:
                        lines.append("Server-Backups:")
                        for name in backup_names:
                            lines.append(f" - {name}")
                    if not backup_names:
                        lines.append("Kein Server-Backup erstellt, weil keine vorhandene routes-Datei gefunden wurde.")
                    if int(info.get("cleanup_deleted", 0) or 0):
                        lines.append(f"Alte Server-Backups gelöscht: {info.get('cleanup_deleted')}")
                    self.after(0, lambda: result_var.set("\n".join(lines)))
                    self.after(0, load_server_backups)
                    self.after(0, lambda: messagebox.showinfo("routes.php hochladen", "routes-Dateien wurden hochgeladen.", parent=dialog))
                except Exception as exc:
                    self.after(0, lambda error=str(exc): result_var.set(f"Upload fehlgeschlagen: {error}"))
                    self.after(0, lambda error=str(exc): messagebox.showerror("routes.php hochladen", f"Upload fehlgeschlagen:\n{error}", parent=dialog))
                finally:
                    self.after(0, lambda: [child.configure(state="normal") for child in buttons.winfo_children()])

            threading.Thread(target=worker, daemon=True).start()

        def delete_selected_backups() -> None:
            names = [str(iid) for iid in backup_tree.selection()]
            if not names:
                messagebox.showinfo("Server-Backups", "Bitte zuerst Backup-Dateien auswählen.", parent=dialog)
                return
            if not messagebox.askyesno("Server-Backups löschen", f"{len(names)} ausgewählte Server-Backup(s) löschen?", parent=dialog):
                return
            try:
                deleted = self.delete_routes_backups_via_ftp(names)
                load_server_backups()
                messagebox.showinfo("Server-Backups", f"{deleted} Backup-Datei(en) gelöscht.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Server-Backups", f"Backups konnten nicht gelöscht werden:\n{exc}", parent=dialog)

        def cleanup_old_backups() -> None:
            if not messagebox.askyesno("Server-Backups bereinigen", "Nur die letzten 3 routes-Backups je Datei behalten und ältere löschen?", parent=dialog):
                return
            try:
                deleted = self.cleanup_old_routes_backups_via_ftp(keep=3)
                load_server_backups()
                messagebox.showinfo("Server-Backups", f"{deleted} alte Backup-Datei(en) gelöscht.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Server-Backups", f"Backups konnten nicht bereinigt werden:\n{exc}", parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, sticky="e", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Backups aktualisieren", command=load_server_backups).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ausgewählte Backups löschen", command=delete_selected_backups).pack(side="left", padx=4)
        ttk.Button(buttons, text="Nur letzte 3 behalten", command=cleanup_old_backups).pack(side="left", padx=4)
        ttk.Button(buttons, text="Sichern und hochladen", command=run_deploy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        load_server_backups()

    def open_operating_mode_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Betriebsmodus")
        try: self.track_window_geometry(dialog, "Betriebsmodus")
        except Exception: pass
        dialog.geometry("560x260")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        ttk.Label(dialog, text="Betriebsmodus", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        info = (
            "Im Produktivbetrieb ist das Zurücksetzen der Bewegungsdaten gesperrt.\n"
            "Im Testbetrieb kann ein Superadmin Bewegungsdaten zurücksetzen."
        )
        ttk.Label(dialog, text=info, wraplength=520).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        mode_var = tk.StringVar(value="production")
        ttk.Radiobutton(dialog, text="Produktivbetrieb", variable=mode_var, value="production").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        ttk.Radiobutton(dialog, text="Testbetrieb", variable=mode_var, value="test").grid(row=3, column=0, sticky="w", padx=12, pady=4)
        status_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status_var, foreground="#444444").grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 8))

        def refresh() -> None:
            try:
                resp = self.api.operating_mode(self.api_token)
                mode_var.set(str(resp.get("mode") or "production"))
                status_var.set(f"Aktueller Modus: {resp.get('label') or mode_var.get()}")
            except Exception as exc:
                status_var.set(f"Betriebsmodus konnte nicht geladen werden: {exc}")

        def save() -> None:
            mode = mode_var.get()
            if mode == "test" and not messagebox.askyesno(
                "Testbetrieb aktivieren",
                "Testbetrieb aktivieren?\n\nIm Testbetrieb ist das Zurücksetzen der Bewegungsdaten möglich.",
                parent=dialog,
            ):
                return
            try:
                resp = self.api.set_operating_mode(self.api_token, mode)
                status_var.set(f"Aktueller Modus: {resp.get('label') or mode}")
                messagebox.showinfo("Betriebsmodus", "Betriebsmodus wurde gespeichert.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Betriebsmodus", f"Betriebsmodus konnte nicht gespeichert werden:\n{exc}", parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, sticky="e", padx=12, pady=(4, 12))
        ttk.Button(buttons, text="Aktualisieren", command=refresh).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        refresh()

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
            "Lokale JSON-Sicherungsdateien ohne passenden API-Datensatz werden nach dem Reset automatisch gelöscht.\n\n"
            "Bitte vorher ein MySQL-Backup erstellen."
        )
        ttk.Label(dialog, text=warning, wraplength=720, foreground="#8a0000").grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        mode_var = tk.StringVar(value="Betriebsmodus wird geprüft ...")
        mode_allows_reset = {"value": False}
        ttk.Label(dialog, textvariable=mode_var, foreground="#8a0000").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))
        include_mail_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Mail-Versandhistorie ebenfalls löschen", variable=include_mail_var).grid(row=2, column=0, sticky="w", padx=12, pady=(4, 8))
        ttk.Label(dialog, text="Zum Bestätigen exakt eingeben: DATENBANK ZURUECKSETZEN").grid(row=3, column=0, sticky="w", padx=12, pady=(8, 4))
        confirm_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=confirm_var).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))
        result_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=result_var, wraplength=720).grid(row=5, column=0, sticky="ew", padx=12, pady=(4, 8))
        buttons = ttk.Frame(dialog)
        buttons.grid(row=6, column=0, sticky="e", padx=12, pady=12)
        def run_reset() -> None:
            if not mode_allows_reset["value"]:
                messagebox.showwarning("Produktivbetrieb", "Der Datenbank-Reset ist nur im Testbetrieb erlaubt.", parent=dialog)
                return
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
                cleanup = self.delete_orphan_local_metadata_backups()
                lines.append(f"verwaiste lokale JSON-Sicherungen gelöscht: {cleanup.get('deleted', 0)}")
                errors = cleanup.get("errors", [])
                if isinstance(errors, list) and errors:
                    lines.append(f"Fehler bei JSON-Bereinigung: {len(errors)}")
                result_var.set("\n".join(lines))
                self.refresh_dashboard()
                self.refresh_admin_uploads(show_message=False)
                messagebox.showinfo("Datenbank zurücksetzen", "Zurücksetzen abgeschlossen. Verwaiste lokale JSON-Sicherungen wurden bereinigt.", parent=dialog)
            except ApiError as exc:
                messagebox.showerror("Datenbank zurücksetzen", f"Zurücksetzen fehlgeschlagen:\n{exc}", parent=dialog)
        reset_button = ttk.Button(buttons, text="Datenbank zurücksetzen", command=run_reset)
        reset_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)

        def refresh_mode() -> None:
            try:
                resp = self.api.operating_mode(self.api_token)
                mode = str(resp.get("mode") or "production")
                label = str(resp.get("label") or mode)
                mode_allows_reset["value"] = mode == "test"
                mode_var.set(f"Aktueller Betriebsmodus: {label}")
                reset_button.configure(state="normal" if mode == "test" else "disabled")
            except Exception as exc:
                mode_allows_reset["value"] = False
                mode_var.set(f"Betriebsmodus konnte nicht geprüft werden: {exc}")
                reset_button.configure(state="disabled")
        refresh_mode()
