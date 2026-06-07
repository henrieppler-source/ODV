from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from .api_client import ApiError
from .app_logging import app_log_exception
from .database import add_history
from .models import HistoryEntry
from .users import ROLES, role_allows_user_management


class UserAdminMixin:
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

        state = {"devices": [], "device_lookup": {}, "sessions": []}
        load_state = {"id": 0}
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(dialog, textvariable=status_var, foreground="#666666")
        status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))
        refresh_button = None
        end_selected_session_button = None
        block_device_button = None
        unblock_device_button = None

        def _set_busy_controls(disabled: bool) -> None:
            target_state = "disabled" if disabled else "normal"
            for btn in (refresh_button, end_selected_session_button, block_device_button, unblock_device_button):
                if btn is not None:
                    try:
                        btn.configure(state=target_state)
                    except Exception:
                        pass

        def refresh() -> None:
            if not dialog.winfo_exists():
                return
            load_state["id"] += 1
            request_id = load_state["id"]
            status_var.set("Lade Sitzungs- und Gerätedaten …")
            _set_busy_controls(True)
            for tree in (sess_tree, dev_tree):
                for iid in tree.get_children():
                    tree.delete(iid)

            def apply_error(exc: Exception) -> None:
                if not dialog.winfo_exists():
                    return
                if request_id != load_state["id"]:
                    return
                _set_busy_controls(False)
                status_var.set("Daten konnten nicht geladen werden.")
                messagebox.showerror("Sitzungen und Geräte", f"Daten konnten nicht geladen werden:\n{exc}", parent=dialog)

            def apply_data(data: dict) -> None:
                if not dialog.winfo_exists():
                    return
                if request_id != load_state["id"]:
                    return
                state["devices"] = list(data.get("devices", []))
                state["device_lookup"] = {}
                state["sessions"] = list(data.get("sessions", []))
                for tree in (sess_tree, dev_tree):
                    for iid in tree.get_children():
                        tree.delete(iid)
                for row in state["sessions"]:
                    sess_tree.insert(
                        "",
                        "end",
                        iid=str(row.get("session_id")),
                        values=(
                            row.get("session_id", ""),
                            row.get("display_name", ""),
                            row.get("device_name", ""),
                            row.get("app_version", ""),
                            row.get("ip_address", ""),
                            row.get("started_at", ""),
                            row.get("last_seen_at", ""),
                            row.get("expires_at", ""),
                        ),
                    )
                for idx, row in enumerate(state["devices"]):
                    iid = str(row.get("device_id") or idx)
                    state["device_lookup"][iid] = row
                    dev_tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(
                            row.get("user_id", ""),
                            row.get("display_name", ""),
                            row.get("device_id", ""),
                            row.get("device_name", ""),
                            row.get("windows_user", ""),
                            row.get("app_version", ""),
                            row.get("last_ip", ""),
                            row.get("first_seen_at", ""),
                            row.get("last_login_at", ""),
                            "ja" if int(row.get("is_blocked", 0) or 0) == 1 else "nein",
                        ),
                    )
                status_var.set(f"{len(state['sessions'])} Sitzung(en), {len(state['devices'])} Gerät(er)")
                _set_busy_controls(False)

            def worker() -> None:
                try:
                    data = self.api.list_sessions_and_devices(self.api_token)
                except Exception as exc:
                    app_log_exception("Sitzungsdaten konnten nicht geladen werden", exc)
                    self.after(0, lambda exc=exc: apply_error(exc))
                    return
                self.after(0, lambda data=data: apply_data(data))

            threading.Thread(target=worker, daemon=True).start()

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
                return state["device_lookup"].get(sel[0])
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
        refresh_button = ttk.Button(buttons, text="Aktualisieren", command=refresh)
        refresh_button.pack(side="left")
        end_selected_session_button = ttk.Button(buttons, text="Ausgewählte Sitzung beenden", command=end_selected_session)
        end_selected_session_button.pack(side="left", padx=8)
        block_device_button = ttk.Button(buttons, text="Gerät sperren", command=lambda: set_blocked(True))
        block_device_button.pack(side="left", padx=8)
        unblock_device_button = ttk.Button(buttons, text="Gerät freigeben", command=lambda: set_blocked(False))
        unblock_device_button.pack(side="left", padx=8)
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
        nextcloud_username_var = tk.StringVar()
        nextcloud_password_var = tk.StringVar()
        role_var = tk.StringVar(value="Ortschronist")
        place_var = tk.StringVar()
        active_var = tk.BooleanVar(value=True)
        selected_user_id = {"id": None}
        api_users: list[dict] = []
        users_by_iid: dict[str, dict] = {}
        refresh_state = {"id": 0}
        users_status_var = tk.StringVar(value="")
        users_refresh_button: tk.Button | None = None
        new_user_button: tk.Button | None = None
        save_user_button: tk.Button | None = None
        deactivate_user_button: tk.Button | None = None

        labels = [
            ("Name:", name_var),
            ("Benutzername:", username_var),
            ("E-Mail:", email_var),
            ("Passwort:", password_var),
            ("Nextcloud-Benutzername:", nextcloud_username_var),
            ("Nextcloud-Passwort:", nextcloud_password_var),
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

        ttk.Checkbutton(form, text="Benutzer aktiv", variable=active_var).grid(row=8, column=0, columnspan=2, sticky="w", pady=(6, 4))
        hint = ttk.Label(
            form,
            text=(
                "Die Benutzerverwaltung arbeitet jetzt direkt mit der zentralen MySQL-Datenbank über die API.\n"
                "*** bedeutet: Passwort ist gespeichert. Nur bei Passwortänderung ein neues Passwort eingeben. Bei neuen Benutzern ist ein Passwort Pflicht."
            ),
            wraplength=360,
        )
        hint.grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 12))

        perm_frame = ttk.LabelFrame(form, text="Rechte / Hinweise", padding=6)
        perm_frame.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(4, 8))
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
        users_status_label = ttk.Label(list_frame, textvariable=users_status_var, foreground="#666666")
        users_status_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

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
            if user_id <= 0:
                return
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
            nextcloud_username_var.set("")
            nextcloud_password_var.set("")
            role_var.set("Ortschronist")
            place_var.set("")
            active_var.set(True)
            set_permission_widgets(default_permission_values("Ortschronist"))
            try:
                tree.selection_remove(tree.selection())
            except tk.TclError:
                pass

        def _set_users_busy_controls(disabled: bool) -> None:
            target_state = "disabled" if disabled else "normal"
            for btn in (users_refresh_button, new_user_button, save_user_button, deactivate_user_button):
                if btn is not None:
                    try:
                        btn.configure(state=target_state)
                    except Exception:
                        pass

        def refresh_tree(select_id: int | None = None):
            nonlocal api_users, users_by_iid
            if not dialog.winfo_exists():
                return
            refresh_state["id"] += 1
            request_id = refresh_state["id"]
            users_status_var.set("Lade Benutzerdaten …")
            _set_users_busy_controls(True)
            for item in tree.get_children():
                tree.delete(item)

            def apply_error(exc: Exception) -> None:
                if not dialog.winfo_exists():
                    return
                if request_id != refresh_state["id"]:
                    return
                _set_users_busy_controls(False)
                users_status_var.set("Benutzer konnten nicht geladen werden.")
                messagebox.showerror("Benutzerverwaltung", f"Benutzer konnten nicht geladen werden:\n{exc}", parent=dialog)

            def apply_data(users: list[dict]) -> None:
                if not dialog.winfo_exists():
                    return
                if request_id != refresh_state["id"]:
                    return
                api_users = users
                users_by_iid = {}
                for item in tree.get_children():
                    tree.delete(item)
                for user in api_users:
                    user_id_text = (
                        str(user.get("id") or user.get("user_id") or user.get("uid") or user.get("userId") or user.get("api_id") or "").strip()
                    )
                    if not user_id_text:
                        user_id_text = f"row-{len(users_by_iid)}"
                    uid = user_id_text
                    suffix = 1
                    while tree.exists(uid):
                        suffix += 1
                        uid = f"{user_id_text}#{suffix}"
                    tree.insert("", "end", iid=uid, values=(
                        user.get("display_name", ""),
                        user.get("username", ""),
                        user.get("email", "") or "",
                        api_role_label(str(user.get("role", ""))),
                        user.get("place", "") or "",
                        "ja" if int(user.get("is_active", 0) or 0) == 1 else "nein",
                        user.get("last_login_at", "") or "",
                    ))
                    users_by_iid[uid] = user
                if select_id is not None and tree.exists(str(select_id)):
                    tree.selection_set(str(select_id))
                    tree.see(str(select_id))
                    load_selected()
                users_status_var.set(f"{len(api_users)} Benutzer geladen")
                _set_users_busy_controls(False)

            def worker() -> None:
                try:
                    response = self.api.list_users(self.api_token)
                    users = list(response.get("users", []))
                except Exception as exc:
                    app_log_exception("Benutzerliste konnte nicht geladen werden", exc)
                    self.after(0, lambda exc=exc: apply_error(exc))
                    return
                self.after(0, lambda users=users: apply_data(users))

            threading.Thread(target=worker, daemon=True).start()

        def _to_int_user_id(user_id: object) -> int:
            text = str(user_id or "").strip()
            if not text:
                return 0
            try:
                return int(text)
            except (TypeError, ValueError):
                return 0

        def find_loaded_user(user_id: str) -> dict | None:
            for user in api_users:
                if str(user.get("id") or user.get("user_id") or user.get("uid") or user.get("userId") or user.get("api_id") or "").strip() == user_id:
                    return user
            return None

        def to_bool_value(value: object, default: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return int(value) == 1
            text = str(value).strip().lower()
            if not text:
                return default
            if text in {"1", "true", "yes", "y", "on", "ja"}:
                return True
            if text in {"0", "false", "no", "n", "off", "nein"}:
                return False
            if text in {"true", "false"}:
                return text == "true"
            return default

        def _coerce_user_record(user: object, fallback_values: tuple | None = None) -> dict:
            if isinstance(user, dict):
                return user
            if fallback_values is None:
                return {}
            return {
                "display_name": str(fallback_values[0] or ""),
                "username": str(fallback_values[1] or ""),
                "email": str(fallback_values[2] or ""),
                "role": str(fallback_values[3] or ""),
                "place": str(fallback_values[4] or ""),
                "is_active": 1 if str(fallback_values[5]).strip().lower() in {"ja", "true", "1", "yes"} else 0,
            }

        def update_selected_user_fields(user: dict) -> None:
            name_var.set(str(user.get("display_name", "") or ""))
            username_var.set(str(user.get("username", "") or ""))
            email_var.set(str(user.get("email", "") or ""))
            password_saved = to_bool_value(user.get("password_saved"), default=True)
            password_var.set("***" if password_saved else "")
            nextcloud_username_var.set(str(user.get("nextcloud_username", "") or ""))
            nextcloud_password_var.set("***" if to_bool_value(user.get("nextcloud_password_saved")) else "")
            role_var.set(api_role_label(str(user.get("role", "ortschronist"))))
            place_var.set(str(user.get("place", "") or ""))
            active_var.set(to_bool_value(user.get("is_active", 1), default=False))
            load_user_permissions(_to_int_user_id(user.get("id")), role_var.get())

        def load_selected(_event=None):
            iid = None
            if _event is not None and hasattr(_event, "y"):
                iid = tree.identify_row(_event.y)
            if not iid:
                selected = tree.selection()
                if selected:
                    iid = selected[0]
            if not iid:
                iid = tree.focus()
            if not iid:
                return
            user_id = str(iid).strip()
            selected_user_id["id"] = user_id
            user = users_by_iid.get(iid)
            if user is None:
                try:
                    index = tree.get_children().index(iid)
                    if 0 <= index < len(api_users):
                        user = api_users[index]
                except Exception:
                    user = None
            if user is None:
                item = tree.item(iid, "values")
                if item:
                    if api_users and item[1]:
                        candidate = str(item[1]).strip()
                        for candidate_user in api_users:
                            if str(candidate_user.get("username", "")) == candidate:
                                user = candidate_user
                                break
            if user is None:
                item = tree.item(iid, "values")
                if item:
                    user = {
                        "display_name": str(item[0] or ""),
                        "username": str(item[1] or ""),
                        "email": str(item[2] or ""),
                        "role": str(item[3] or ""),
                        "place": str(item[4] or ""),
                        "is_active": 1 if str(item[5]).strip().lower() in {"ja", "true", "1", "yes"} else 0,
                    }
            if not user:
                users_status_var.set("Auswahl konnte nicht aufgelöst werden.")
                return
            try:
                item_values = tree.item(iid, "values")
                users_status_var.set(f"Ausgewählt: {str(item_values[1] if item_values else '')}")
                update_selected_user_fields(_coerce_user_record(user, item_values))
            except Exception as exc:
                app_log_exception("Benutzerdaten konnten nicht geladen werden", exc)
                messagebox.showerror("Benutzerverwaltung", f"Ausgewählten Benutzer können nicht geladen werden:\n{exc}", parent=dialog)
                clear_form()

        def build_payload(include_password: bool) -> dict:
            name = name_var.get().strip()
            username = username_var.get().strip()
            password = password_var.get()
            nextcloud_username = nextcloud_username_var.get().strip()
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
                "nextcloud_username": nextcloud_username,
                "role": self.local_role_to_api(role),
                "place": place,
                "is_active": bool(active_var.get()),
            }
            nextcloud_password = nextcloud_password_var.get().strip()
            if nextcloud_password and nextcloud_password != "***":
                payload["nextcloud_password"] = nextcloud_password
            if include_password:
                if not password or password == "***":
                    raise ValueError("Bitte für neue Benutzer ein Passwort erfassen.")
                payload["password"] = password
            elif password and password != "***":
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
                    nextcloud_username = nextcloud_username_var.get().strip()
                    if nextcloud_username:
                        payload["nextcloud_username"] = nextcloud_username
            # Schutz gegen Selbst-Deaktivierung: Der angemeldete Benutzer darf
            # sich nicht versehentlich über die Benutzerverwaltung deaktivieren.
                    current_username = self.username_var.get().strip().lower()
                    edited_username = username_var.get().strip().lower()
                    if edited_username == current_username and not bool(payload.get("is_active", True)):
                        active_var.set(True)
                        messagebox.showwarning(
                            "Nicht möglich",
                            "Der aktuell angemeldete Benutzer kann sich nicht selbst deaktivieren.",
                            parent=dialog,
                        )
                        return
                    user_id_int = _to_int_user_id(user_id)
                    if user_id_int <= 0:
                        messagebox.showerror("Benutzer speichern", "Ungültige Benutzerkennung.", parent=dialog)
                        return
                    self.api.update_user(self.api_token, user_id_int, payload)
                    self.api.update_folder_permissions(self.api_token, user_id_int, current_permission_payload())
                    messagebox.showinfo("Benutzerverwaltung", "Benutzer wurde in der zentralen Datenbank gespeichert.", parent=dialog)
                    refresh_tree(select_id=user_id_int)
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
                user_id_int = _to_int_user_id(user_id)
                if user_id_int <= 0:
                    messagebox.showerror("Benutzer deaktivieren", "Ungültige Benutzerkennung.", parent=dialog)
                    return
                self.api.update_user(self.api_token, user_id_int, payload)
                active_var.set(False)
                refresh_tree(select_id=user_id_int)
                add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Benutzer deaktiviert API", username_var.get().strip()))
                self.refresh_history()
            except (ValueError, ApiError) as exc:
                messagebox.showerror("Benutzerverwaltung", str(exc), parent=dialog)

        btns = ttk.Frame(form)
        btns.grid(row=11, column=0, columnspan=2, sticky="ew", pady=8)
        new_user_button = ttk.Button(btns, text="Neu", command=clear_form)
        new_user_button.pack(side="left", padx=4)
        save_user_button = ttk.Button(btns, text="Benutzer speichern", command=save_user)
        save_user_button.pack(side="left", padx=4)
        deactivate_user_button = ttk.Button(btns, text="Benutzer deaktivieren", command=deactivate_user)
        deactivate_user_button.pack(side="left", padx=4)
        users_refresh_button = ttk.Button(btns, text="Liste aktualisieren", command=lambda: refresh_tree())
        users_refresh_button.pack(side="left", padx=4)

        tree.bind("<<TreeviewSelect>>", load_selected)
        tree.bind("<ButtonRelease-1>", lambda _e: load_selected())
        refresh_tree()
        if tree.get_children():
            first = tree.get_children()[0]
            tree.selection_set(first)
            load_selected()
