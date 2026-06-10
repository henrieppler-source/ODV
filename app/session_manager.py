from __future__ import annotations

import getpass
import os
import platform
import socket
import uuid

import tkinter as tk
from tkinter import messagebox, ttk

from .app_logging import app_log_exception
from .api_client import APIClient, ApiError
from .config import save_config
from .database import add_history
from .models import HistoryEntry
from .users import find_user_by_username, role_allows_admin


class SessionManagerMixin:
    @staticmethod
    def _api_base_url(config_data: dict) -> str:
        return str(config_data.get("api_url", "https://ortschronik.info/api"))

    def _apply_login_response(self, response: dict, username: str, parent_for_errors: tk.Misc | None = None) -> bool:
        try:
            self.api_token = str(response.get("token", ""))
            self.config_data["api_token"] = self.api_token
            self.config_data["api_token_expires_at"] = str(response.get("expires_at", ""))
            self.config_data["current_username"] = username
            user = self.api_user_to_local(response.get("user", {}))
            self.set_current_user(user, persist=True)
            self.handle_login_session_notice(response)
            self.report_current_device_version()
            return True
        except Exception as exc:
            if parent_for_errors is not None:
                messagebox.showerror("Anmeldung", str(exc), parent=parent_for_errors)
            else:
                app_log_exception("Login-Nachbearbeitung fehlgeschlagen", exc)
            return False

    def _submit_login(self, username: str, password: str, parent_for_errors) -> bool:
        if not username or not password:
            messagebox.showerror("Anmeldung", "Bitte Benutzername und Passwort eingeben.", parent=parent_for_errors)
            return False
        try:
            self.api = APIClient(self._api_base_url(self.config_data))
            response = self.api.login(username, password, self.get_device_info())
            return self._apply_login_response(response, username, parent_for_errors)
        except ApiError as exc:
            app_log_exception("Anmeldung fehlgeschlagen", exc, username=username)
            messagebox.showerror("Anmeldung", str(exc), parent=parent_for_errors)
            return False

    def api_user_to_local(self, user: dict) -> dict:
        return {
            "display_name": user.get("display_name") or user.get("name") or user.get("username") or "Ortschronist/in",
            "username": user.get("username") or "",
            "email": user.get("email") or "",
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
            "app_version": self.APP_VERSION,
        }

    def report_current_device_version(self) -> None:
        """Meldet die aktuelle ODV-Version an die API, damit Sitzungen/Geräte nach Updates aktuell bleiben."""
        try:
            if self.api_token:
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
        self.api = APIClient(self._api_base_url(self.config_data))
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

        self.title(f"{self.APP_NAME} ({self.APP_SHORT_NAME}) {self.APP_VERSION} – Anmeldung")
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

        ttk.Label(frame, text=self.APP_NAME, font=("", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(frame, text=f"{self.APP_SHORT_NAME} · {self.APP_VERSION}").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 18))

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
            if self._submit_login(username, password, self):
                result["ok"] = True
                done.set(True)

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

        ttk.Label(dialog, text=f"{self.APP_NAME} ({self.APP_SHORT_NAME})", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
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
            if self._submit_login(username, password, dialog):
                result["ok"] = True
                dialog.destroy()

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
        self.config_data["current_email"] = str(self.config_data.get("current_email", "") or "")
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
        self.email_var.set(user.get("email", "") or "")
        self.role_var.set(user.get("role", "Ortschronist"))
        self.role_label_var.set(self.role_var.get())
        self.place_var.set(user.get("place", ""))
        # Beim Benutzerwechsel muss der Ort im Upload-Formular sofort zum neu angemeldeten Benutzer passen.
        if "place" in self.meta_vars:
            self.meta_vars["place"].set(self.place_var.get().strip())
        self.config_data["display_name"] = self.display_name_var.get()
        self.config_data["current_username"] = self.username_var.get()
        self.config_data["current_email"] = self.email_var.get()
        self.config_data["current_role"] = self.role_var.get()
        self.config_data["current_place"] = self.place_var.get()
        self.load_current_folder_permissions()
        if persist:
            save_config(self.config_data)

    def refresh_window_title(self) -> None:
        name = self.config_data.get("display_name") or "Ortschronist/in"
        role = self.config_data.get("current_role") or ""
        self.title(f"{self.APP_NAME} ({self.APP_SHORT_NAME}) {self.APP_VERSION} API – {name} ({role})")

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
        ttk.Button(buttons, text="Ordner prüfen", command=lambda: self.load_writable_folders(show_message=True, async_scan=True)).pack(side="left", padx=6)
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
        return self.role_var.get().strip()

    def is_current_admin(self) -> bool:
        return role_allows_admin(self.current_role())

    def apply_selected_user(self) -> None:
        # In der API-Version ist die angemeldete Person bereits durch /login oder /me gesetzt.
        # Die frühere lokale users.json darf diese Daten nicht mehr überschreiben.
        if self.current_user:
            self.role_label_var.set(self.role_var.get())
            if "place" in self.meta_vars:
                self.meta_vars["place"].set(self.place_var.get().strip())
        else:
            username = self.username_var.get().strip() or self.config_data.get("current_username", "")
            user = find_user_by_username(self.users, username) if username else None
            if user:
                self.set_current_user(user, persist=True)
            else:
                self.role_label_var.set(self.role_var.get())
        self.refresh_window_title()
        if self.notebook and self.admin_tab:
            try:
                self.configure_admin_actions_for_role()
            except tk.TclError:
                pass
        # Menü je nach Rolle neu aufbauen, damit Admin-Menü nur Superadmins sehen.
        if self.notebook:
            self.create_menu()

    def require_admin(self) -> bool:
        self.apply_selected_user()
        if self.is_current_admin():
            return True
        messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Admins freigegeben.")
        return False
