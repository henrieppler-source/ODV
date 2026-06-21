from __future__ import annotations

import base64
import calendar
import mimetypes
from datetime import date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import webbrowser

from .api_client import ApiError
from .app_logging import app_log, app_log_exception
from .mail_manager_utils import (
    build_stable_user_id as _mm_build_stable_user_id,
    coerce_user_records as _mm_coerce_user_records,
    extract_user_active as _mm_extract_user_active,
    extract_user_email as _mm_extract_user_email,
    extract_numeric_user_id as _mm_extract_numeric_user_id,
    normalize_mail_markup as _mm_normalize_mail_markup,
    render_mail_html as _mm_render_mail_html,
)
from .mail_manager_visibility_utils import (
    mail_group_matches_user as _mmvu_mail_group_matches_user,
    mail_user_context as _mmvu_mail_user_context,
)
from .mail_manager_recipients_utils import (
    build_mail_attachments as _mmra_build_mail_attachments,
    collect_mail_recipients as _mmra_collect_mail_recipients,
)
from .mail_manager_history_utils import (
    format_mail_history_detail as _mmh_format_mail_history_detail,
    load_mail_history_rows as _mmh_load_mail_history_rows,
    summarize_mail_history_documents as _mmh_summarize_mail_history_documents,
)
from .mail_manager_groups_utils import (
    build_mail_group_payload as _mmg_build_mail_group_payload,
    group_display_label as _mmg_group_display_label,
    parse_external_members_text as _mmg_parse_external_members_text,
    render_external_members_text as _mmg_render_external_members_text,
    selected_member_ids as _mmg_selected_member_ids,
)
from .mail_manager_templates_utils import (
    get_mail_text_templates as _mmt_get_mail_text_templates,
    set_mail_text_templates as _mmt_set_mail_text_templates,
    template_labels as _mmt_template_labels,
)
from .mail_manager_send_dialog_utils import (
    open_information_mail_dialog as _mmsd_open_information_mail_dialog,
)
from .users import load_users as load_local_users


class MailManagerMixin:
    @staticmethod
    def _coerce_user_records(payload: object) -> list[dict]:
        return _mm_coerce_user_records(payload)

    @staticmethod
    def _extract_user_email(user: dict) -> str:
        return _mm_extract_user_email(user)

    @staticmethod
    def _extract_user_active(user: dict) -> bool:
        return _mm_extract_user_active(user)

    @staticmethod
    def _build_stable_user_id(item: dict, email: str) -> int:
        return _mm_build_stable_user_id(item, email)

    @staticmethod
    def _extract_numeric_user_id(user: dict, keys: tuple[str, ...] = ("id", "user_id", "uid", "userId")) -> int:
        return _mm_extract_numeric_user_id(user, keys=keys)

    def _maybe_load_users(self, source_callable, *args: object) -> object | None:
        if not callable(source_callable):
            return None
        try:
            return source_callable(*args)
        except TypeError:
            return None
        except Exception:
            return None

    def _append_user_source(self, sources: list[object], source_callable, include_token: bool = False) -> None:
        if include_token and self.api_token:
            payload = self._maybe_load_users(source_callable, self.api_token)
            if payload is not None:
                sources.append(payload)
                return
        payload = self._maybe_load_users(source_callable)
        if payload is not None:
            sources.append(payload)

    def normalize_mail_markup(self, text: str) -> str:
        """Entfernt die leichte /b-Markierung für reine Textausgaben."""
        return _mm_normalize_mail_markup(text)

    def render_mail_html(self, text: str) -> str:
        """Erzeugt eine sehr leichte HTML-Darstellung mit /b.../b als fett."""
        return _mm_render_mail_html(text)

    def get_mail_text_templates(self) -> list[dict]:
        return _mmt_get_mail_text_templates(self.config_data)

    def set_mail_text_templates(self, templates: list[dict]) -> None:
        _mmt_set_mail_text_templates(self.config_data, templates)

    def load_email_users(self) -> list[dict]:
        """Benutzer mit E-Mail-Adresse laden.

        Für die Verteilerverwaltung sollen Bearbeiter dieselbe Benutzerbasis
        sehen wie Admins. Deshalb kombinieren wir API-Daten und lokale
        Benutzerdateien und akzeptieren unterschiedliche Feldnamen für E-Mail
        und Aktiv-Status.
        """
        try:
            sources: list[object] = []
            if self.api_token:
                try:
                    self._append_user_source(sources, self.api.list_users, include_token=True)
                except Exception:
                    pass
            users_source = self.users
            if users_source:
                sources.append(users_source)
            source_result = self._maybe_load_users(load_local_users)
            if source_result is not None:
                sources.append(source_result)

            self._append_user_source(sources, self.load_users, include_token=True)
            self._append_user_source(sources, self.load_all_users, include_token=True)
            self._append_user_source(sources, self.get_users, include_token=True)

            users: list[dict] = []
            seen_ids: set[str] = set()

            for source in sources:
                for user in self._coerce_user_records(source):
                    email = self._extract_user_email(user)
                    if not email:
                        continue
                    if not self._extract_user_active(user):
                        continue

                    identifier = str(
                        user.get("id")
                        or user.get("user_id")
                        or user.get("username")
                        or user.get("display_name")
                        or user.get("name")
                        or email
                    ).strip().lower()
                    if identifier in seen_ids:
                        continue
                    seen_ids.add(identifier)

                    item = dict(user)
                    item["email"] = email
                    item["id"] = self._build_stable_user_id(item, email)
                    users.append(item)

            users.sort(
                key=lambda item: (
                    str(item.get("display_name") or item.get("name") or item.get("username") or item.get("email") or "").strip().lower(),
                    str(item.get("email") or "").strip().lower(),
                )
            )
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

    def _mail_user_context(self) -> dict[str, str]:
        return _mmvu_mail_user_context(self, self.config_data)

    def load_visible_mail_groups(self) -> list[dict]:
        """Lädt die für den aktuellen Benutzer sichtbaren Verteiler.

        Admin/Superadmin sehen die komplette Liste. Bearbeiter sehen nur ihre
        eigenen bzw. ortsbezogenen Verteiler.
        """
        groups = self.load_mail_groups()
        if not groups or self.is_current_admin():
            return groups

        ctx = self._mail_user_context()
        visible = [group for group in groups if _mmvu_mail_group_matches_user(group, ctx)]
        return visible or groups



    def format_mail_history_detail(self, item: dict) -> str:
        return _mmh_format_mail_history_detail(item)

    def open_mail_history_dialog(self) -> None:
        """Zeigt die serverseitige Historie der über ODV versendeten Rundmails."""
        if not self.api_token:
            messagebox.showerror("API", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Versandhistorie")
        try: self.track_window_geometry(dialog, "Versandhistorie")
        except Exception: pass
        dialog.geometry("1180x700")
        dialog.transient(self)
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
                rows = _mmh_load_mail_history_rows(self.api, self.api_token, limit=500)
            except ApiError as exc:
                messagebox.showerror("Versandhistorie", f"Versandhistorie konnte nicht geladen werden:\n{exc}", parent=dialog)
                return
            for i, item in enumerate(rows):
                docs = _mmh_summarize_mail_history_documents(item.get("documents") or item.get("links") or "")
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


    def open_mail_group_management_dialog(self) -> None:
        if not self.api_token:
            messagebox.showerror("Verteiler", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
            return
        users = self.load_email_users()
        groups = self.load_visible_mail_groups()
        is_admin = self.is_current_admin()

        dialog = tk.Toplevel(self)
        dialog.title("Verteiler verwalten")
        try: self.track_window_geometry(dialog, "Verteiler verwalten")
        except Exception: pass
        dialog.geometry("1060x720")
        dialog.transient(self)
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
            uid = MailManagerMixin._extract_numeric_user_id(user)
            if uid == 0:
                continue
            var = tk.BooleanVar(value=False)
            member_vars[uid] = var
            label = f"{user.get('display_name','')} <{user.get('email','')}> ({user.get('place','') or user.get('role','')})"
            ttk.Checkbutton(members_inner, text=label, variable=var).grid(row=idx, column=0, sticky="w", pady=1)

        external_frame = ttk.LabelFrame(right, text="Externe Empfänger (Vorname; Name; E-Mail)", padding=6)
        external_text = tk.Text(external_frame, height=5, wrap="none")
        external_scroll = ttk.Scrollbar(external_frame, orient="vertical", command=external_text.yview)
        external_text.configure(yscrollcommand=external_scroll.set)
        if is_admin:
            external_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 4))
            external_frame.columnconfigure(0, weight=1)
            external_text.grid(row=0, column=0, sticky="ew")
            external_scroll.grid(row=0, column=1, sticky="ns")
            ttk.Label(external_frame, text="Eine Zeile je Kontakt, z. B.: Max; Mustermann; max@example.de", foreground="#555555").grid(row=1, column=0, sticky="w", pady=(3, 0))

        def parse_external_members() -> list[dict]:
            return _mmg_parse_external_members_text(external_text.get("1.0", "end"))

        def set_external_members(members: list[dict]) -> None:
            if not is_admin:
                return
            external_text.delete("1.0", "end")
            external_text.insert("1.0", _mmg_render_external_members_text(members))

        def refresh_group_list(select_id: int | None = None):
            group_list.delete(0, "end")
            for g in groups:
                group_list.insert("end", _mmg_group_display_label(g))
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
            members = _mmg_selected_member_ids(g)
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
            payload_group = _mmg_build_mail_group_payload(
                gid,
                name,
                desc_var.get(),
                active_var.get(),
                member_ids,
                parse_external_members() if is_admin else [],
            )
            try:
                # Der Server speichert einzelne Verteiler bereits additiv.
                # Wir senden hier deshalb nur den aktuell bearbeiteten Eintrag,
                # damit Bearbeiter keine fremden Verteiler mitschicken.
                response = self.api.update_mail_groups(self.api_token, [payload_group])
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

    def open_standard_mail_texts_dialog(self) -> None:
        if not self.is_current_admin():
            messagebox.showwarning("Standard-Mail-Texte", "Nur Admins und Superadmins können Standard-Mail-Texte verwalten.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Standard-Mail-Texte verwalten")
        try: self.track_window_geometry(dialog, "Standard-Mail-Texte verwalten")
        except Exception: pass
        dialog.geometry("980x640")
        dialog.transient(self)
        dialog.columnconfigure(0, weight=0)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(0, weight=1)

        templates = [dict(item) for item in self.get_mail_text_templates()]
        selected_index = {"idx": None}

        left = ttk.LabelFrame(dialog, text="Vorlagen", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        template_list = tk.Listbox(left, width=28, exportselection=False)
        template_list.grid(row=0, column=0, sticky="nsew")
        template_scroll = ttk.Scrollbar(left, orient="vertical", command=template_list.yview)
        template_list.configure(yscrollcommand=template_scroll.set)
        template_scroll.grid(row=0, column=1, sticky="ns")
        order_buttons = ttk.Frame(left)
        order_buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        right = ttk.LabelFrame(dialog, text="Vorlage bearbeiten", padding=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(2, weight=1)

        label_var = tk.StringVar()
        label_entry = ttk.Entry(right, textvariable=label_var)
        ttk.Label(right, text="Kurzbezeichnung:").grid(row=0, column=0, sticky="w", pady=4)
        label_entry.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(right, text="Textvorlage:").grid(row=1, column=0, sticky="nw", pady=4)
        text_widget = tk.Text(right, wrap="word", height=18)
        text_widget.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=4)
        text_scroll = ttk.Scrollbar(right, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scroll.set)
        text_scroll.grid(row=2, column=2, sticky="ns")
        ttk.Label(right, text="Platzhalter bleiben erhalten, z. B. {dokumente}, {link}, {datei}.", foreground="#555").grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        def refresh_list(select_idx: int | None = None) -> None:
            template_list.delete(0, "end")
            for item in templates:
                template_list.insert("end", item.get("label", ""))
            if select_idx is not None and 0 <= select_idx < len(templates):
                template_list.selection_set(select_idx)
                template_list.see(select_idx)

        def load_selected(_event=None) -> None:
            sel = template_list.curselection()
            if not sel:
                return
            idx = int(sel[0])
            if idx < 0 or idx >= len(templates):
                return
            selected_index["idx"] = idx
            item = templates[idx]
            label_var.set(str(item.get("label", "")))
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", str(item.get("text", "")))

        def clear_form() -> None:
            selected_index["idx"] = None
            label_var.set("")
            text_widget.delete("1.0", "end")
            try:
                template_list.selection_clear(0, "end")
            except tk.TclError:
                pass

        def save_selected() -> None:
            label = label_var.get().strip()
            text = text_widget.get("1.0", "end").rstrip()
            if not label or not text.strip():
                messagebox.showwarning("Standard-Mail-Texte", "Bitte Kurzbezeichnung und Textvorlage erfassen.", parent=dialog)
                return
            payload = {"label": label, "text": text}
            idx = selected_index.get("idx")
            if idx is None:
                templates.append(payload)
                idx = len(templates) - 1
            else:
                templates[idx] = payload
            self.set_mail_text_templates(templates)
            refresh_list(idx)
            messagebox.showinfo("Standard-Mail-Texte", "Vorlage gespeichert.", parent=dialog)

        def delete_selected() -> None:
            idx = selected_index.get("idx")
            if idx is None or idx < 0 or idx >= len(templates):
                return
            if not messagebox.askyesno("Standard-Mail-Texte", f"Vorlage '{templates[idx].get('label', '')}' wirklich löschen?", parent=dialog):
                return
            del templates[idx]
            self.set_mail_text_templates(templates)
            clear_form()
            refresh_list()

        def move_item(offset: int) -> None:
            idx = selected_index.get("idx")
            if idx is None:
                return
            new_idx = idx + offset
            if new_idx < 0 or new_idx >= len(templates):
                return
            templates[idx], templates[new_idx] = templates[new_idx], templates[idx]
            selected_index["idx"] = new_idx
            self.set_mail_text_templates(templates)
            refresh_list(new_idx)
            load_selected()

        template_list.bind("<<ListboxSelect>>", load_selected)
        ttk.Button(order_buttons, text="▲", width=3, command=lambda: move_item(-1)).pack(side="left", padx=(0, 4))
        ttk.Button(order_buttons, text="▼", width=3, command=lambda: move_item(1)).pack(side="left")

        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Neu", command=clear_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Löschen", command=delete_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right", padx=4)

        refresh_list()
        if templates:
            template_list.selection_set(0)
            load_selected()

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

    def nextcloud_web_link_for_local_path(self, file_path: str, share_expires_at: str = "") -> str:
        """Erzeugt bevorzugt einen öffentlichen Nextcloud-Downloadlink über die API.

        Die App übergibt lokalen Dateipfad und lokales Nextcloud-Stammverzeichnis.
        Der Server rechnet daraus den Remote-Pfad und erstellt mit der Nextcloud-API
        einen Freigabelink. Falls das fehlschlägt, wird kein Ersatzlink erzeugt,
        damit in Rundmails kein irreführender Nextcloud-Ordnerlink landet.
        """
        raw = (file_path or "").strip()
        if not raw:
            return ""
        if self.api.configured() and self.api_token:
            try:
                base = self.base_folder_var.get().strip()
                response = self.api.create_nextcloud_share(self.api_token, raw, base, share_expires_at=share_expires_at.strip())
                return (response.get("download_url") or response.get("share_url") or "").strip()
            except Exception as exc:
                app_log_exception("Nextcloud-Freigabelink konnte nicht erstellt werden", exc)
                messagebox.showwarning(
                    "Nextcloud-Link",
                    "Der öffentliche Nextcloud-Downloadlink konnte nicht automatisch erzeugt werden.\n"
                    f"Fehler: {exc}"
                )
        return ""

    def is_path_under_nextcloud_base(self, file_path: str) -> bool:
        raw = (file_path or "").strip()
        base_text = self.base_folder_var.get().strip()
        if not raw or not base_text:
            return False
        try:
            base = Path(base_text).resolve()
            path = Path(raw).resolve()
            path.relative_to(base)
            return True
        except Exception:
            return False

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

    def collect_mail_recipients(
        self,
        users: list[dict],
        user_list: tk.Listbox | None,
        groups: list[dict],
        group_listbox: tk.Listbox | None,
        manual_recipients: str,
    ) -> list[str]:
        """Ermittelt die Empfängerliste für die Rundmail aus allen Quellen."""
        return _mmra_collect_mail_recipients(users, user_list, groups, group_listbox, manual_recipients)

    def build_mail_attachments(self, file_paths: list[str]) -> list[dict]:
        return _mmra_build_mail_attachments(file_paths, self.build_mail_attachment_payload)

    def open_information_mail_dialog(self) -> None:
        _mmsd_open_information_mail_dialog(self)
