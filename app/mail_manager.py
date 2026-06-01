from __future__ import annotations

import base64
import calendar
import json
import mimetypes
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import webbrowser

from .api_client import ApiError
from .app_logging import app_log, app_log_exception
from .config import save_config


class MailManagerMixin:
    def normalize_mail_markup(self, text: str) -> str:
        """Entfernt die leichte /b-Markierung für reine Textausgaben."""
        import re
        text = text or ""
        return re.sub(r"/b(.*?)/b", lambda m: m.group(1), text, flags=re.S)

    def render_mail_html(self, text: str) -> str:
        """Erzeugt eine sehr leichte HTML-Darstellung mit /b.../b als fett."""
        import html
        import re
        parts: list[str] = []
        last = 0
        raw = text or ""
        for match in re.finditer(r"/b(.*?)/b", raw, flags=re.S):
            if match.start() > last:
                parts.append(html.escape(raw[last:match.start()]))
            parts.append(f"<strong>{html.escape(match.group(1))}</strong>")
            last = match.end()
        if last < len(raw):
            parts.append(html.escape(raw[last:]))
        html_text = "".join(parts)
        html_text = html_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>\n")
        return f"<html><body>{html_text}</body></html>"

    def get_mail_text_templates(self) -> list[dict]:
        templates = self.config_data.get("mail_text_templates", [])
        if not isinstance(templates, list):
            return []
        out: list[dict] = []
        for item in templates:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "") or item.get("name", "") or "").strip()
            text = str(item.get("text", "") or "").strip()
            if label and text:
                out.append({"label": label, "text": text})
        return out

    def set_mail_text_templates(self, templates: list[dict]) -> None:
        cleaned = []
        for item in templates or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "") or item.get("name", "") or "").strip()
            text = str(item.get("text", "") or "").rstrip()
            if label and text:
                cleaned.append({"label": label, "text": text})
        self.config_data["mail_text_templates"] = cleaned
        save_config(self.config_data)

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
                    expires_at = d.get('expires_at') or d.get('share_expires_at') or ''
                    lines.append(f"{i}. Datei: {label}")
                    if link:
                        lines.append(f"   Link: {link}")
                    if expires_at:
                        lines.append(f"   Gültig bis: {expires_at}")
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
                    parts = []
                    for x in docs:
                        if isinstance(x, dict):
                            label = x.get('file') or x.get('filename') or x.get('name') or ''
                            link = x.get('link') or x.get('download_url') or x.get('url') or ''
                            expires_at = x.get('expires_at') or x.get('share_expires_at') or ''
                            text = label or link or str(x)
                            if link and label:
                                text = f"{label}"
                            if expires_at:
                                text += f" (bis {expires_at})"
                            parts.append(text)
                        else:
                            parts.append(str(x))
                    docs = "; ".join(parts)
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
        dialog.grab_set()
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

        buttons = ttk.Frame(dialog)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Neu", command=clear_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Löschen", command=delete_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Hoch", command=lambda: move_item(-1)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Runter", command=lambda: move_item(1)).pack(side="left", padx=4)
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
        einen Freigabelink. Falls das fehlschlägt, wird als Fallback ein Link in die
        Nextcloud-Dateiansicht des Ordners erzeugt.
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
        dialog.rowconfigure(8, weight=1)

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

        def update_group_highlights() -> None:
            highlighted: set[str] = set()
            selected_indices: set[int] = set(group_listbox.curselection() if group_listbox is not None else [])
            for idx, group in enumerate(groups):
                if idx not in selected_indices:
                    continue
                for member in list(group.get("members", []) or []) + list(group.get("external_members", []) or []):
                    email = str(member.get("email", "") or "").strip().lower()
                    if email:
                        highlighted.add(email)
            for idx, user in enumerate(users):
                email = str(user.get("email", "") or "").strip().lower()
                if email and email in highlighted:
                    user_list.itemconfig(idx, background="#fff2bf")
                else:
                    user_list.itemconfig(idx, background="")

        ttk.Label(dialog, text="Verteiler:").grid(row=1, column=0, sticky="nw", padx=10, pady=8)
        group_frame = ttk.Frame(dialog)
        group_frame.grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        group_frame.columnconfigure(0, weight=1)
        group_listbox: tk.Listbox | None = None
        if groups:
            group_listbox = tk.Listbox(group_frame, selectmode="extended", height=min(6, max(3, len(groups))), exportselection=False)
            group_listbox.grid(row=0, column=0, sticky="ew")
            group_scroll = ttk.Scrollbar(group_frame, orient="vertical", command=group_listbox.yview)
            group_listbox.configure(yscrollcommand=group_scroll.set)
            group_scroll.grid(row=0, column=1, sticky="ns")
            for group in groups:
                text = f"{group.get('name','')} ({len(group.get('members', []))} Empfänger)"
                group_listbox.insert("end", text)
            group_listbox.bind("<<ListboxSelect>>", lambda _e: update_group_highlights())
            ttk.Label(group_frame, text="Mehrfachauswahl mit Strg/Shift möglich.", foreground="#555").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
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
        ttk.Label(fields, text="Antwort an:").grid(row=1, column=0, sticky="w", pady=4)
        reply_to_var = tk.StringVar()
        ttk.Entry(fields, textvariable=reply_to_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(fields, text="Verfallsdatum:").grid(row=2, column=0, sticky="w", pady=4)
        share_expires_at_var = tk.StringVar(value=date.today().isoformat())
        expiry_frame = ttk.Frame(fields)
        expiry_frame.grid(row=2, column=1, sticky="w", pady=4)
        expiry_entry = ttk.Entry(expiry_frame, textvariable=share_expires_at_var, width=16)
        expiry_entry.pack(side="left")
        ttk.Button(expiry_frame, text="Kalender", width=9, command=lambda: open_date_picker()).pack(side="left", padx=(4, 0))
        ttk.Button(expiry_frame, text="Heute", width=7, command=lambda: share_expires_at_var.set(date.today().isoformat())).pack(side="left", padx=(4, 0))
        ttk.Label(fields, text="Dokumente / Anhänge:").grid(row=3, column=0, sticky="nw", pady=4)
        doc_path_var = tk.StringVar()
        link_var = tk.StringVar()
        selected_docs: list[str] = []
        generated_links: dict[str, str] = {}
        doc_frame = ttk.Frame(fields)
        doc_frame.grid(row=3, column=1, sticky="ew", pady=4)
        doc_frame.columnconfigure(1, weight=1)
        ttk.Button(doc_frame, text="+", width=3, command=lambda: add_doc()).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(doc_frame, textvariable=doc_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(doc_frame, text="Entfernen", command=lambda: remove_selected_doc()).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(doc_frame, text="Leeren", command=lambda: clear_docs()).grid(row=0, column=3, padx=(6, 0))
        doc_list = tk.Listbox(doc_frame, height=4, exportselection=False)
        doc_list.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Label(doc_frame, text="Mit + können Dokumente nacheinander hinzugefügt werden. Bei Downloadlink werden alle ausgewählten Dateien als Linkliste in die Mail geschrieben.", foreground="#555").grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(fields, text="Dokumentenliste:").grid(row=4, column=0, sticky="nw", pady=4)
        link_frame = ttk.Frame(fields)
        link_frame.grid(row=4, column=1, sticky="ew", pady=4)
        link_frame.columnconfigure(0, weight=1)
        link_text, link_text_frame = self.make_scrolled_text(link_frame, height=5, wrap="word")
        link_text_frame.grid(row=0, column=0, sticky="ew")
        ttk.Button(link_frame, text="Downloadlinks erzeugen", command=lambda: refresh_document_block(force_links=True)).grid(row=0, column=1, padx=(6, 0), sticky="n")
        ttk.Label(fields, text="Standardtext:").grid(row=6, column=0, sticky="w", pady=4)
        template_var = tk.StringVar()
        template_names = [item.get("label", "") for item in self.get_mail_text_templates()]
        template_frame = ttk.Frame(fields)
        template_frame.grid(row=6, column=1, sticky="ew", pady=4)
        template_frame.columnconfigure(0, weight=1)
        template_combo = ttk.Combobox(template_frame, textvariable=template_var, values=template_names, state="readonly")
        template_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(template_frame, text="Laden", width=8, command=lambda: apply_selected_template()).grid(row=0, column=1, padx=(6, 0))

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
            expiry = share_expires_at_var.get().strip()
            if send_mode_var.get() == "link" and expiry:
                parts.append(f"Gültig bis: {expiry}")
                parts.append("")
            for path in selected_docs:
                name = Path(path).name
                link = generated_links.get(path, "")
                if force_links or send_mode_var.get() == "link":
                    if not link:
                        link = self.nextcloud_web_link_for_local_path(path, share_expires_at_var.get().strip())
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

        ttk.Label(dialog, text="Text:").grid(row=7, column=0, sticky="nw", padx=10, pady=4)
        body, body_frame = self.make_scrolled_text(dialog, height=18, wrap="word")
        body_frame.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=10, pady=4)
        body.insert("1.0", "Liebe Ortschronistinnen und Ortschronisten,\n\n"
                         "es liegt eine neue Information / Einladung vor.\n\n"
                         "DOKUMENTE:\n{dokumente}\n\n"
                         "Viele Grüße\n"
                         f"{self.display_name_var.get().strip() or 'Ortschronisten'}")

        def apply_selected_template() -> None:
            label = template_var.get().strip()
            if not label:
                return
            for item in self.get_mail_text_templates():
                if item.get("label", "") == label:
                    body.delete("1.0", "end")
                    body.insert("1.0", item.get("text", ""))
                    refresh_document_block(force_links=False)
                    return

        template_combo.bind("<<ComboboxSelected>>", lambda _e: apply_selected_template())

        def open_date_picker() -> None:
            try:
                current = date.fromisoformat(share_expires_at_var.get().strip())
            except Exception:
                current = date.today()
            state = {"year": current.year, "month": current.month}
            picker = tk.Toplevel(dialog)
            picker.title("Datum wählen")
            picker.transient(dialog)
            picker.grab_set()
            picker.resizable(False, False)
            picker.columnconfigure(0, weight=1)

            header = ttk.Frame(picker, padding=8)
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(1, weight=1)
            month_label = ttk.Label(header, text="")
            month_label.grid(row=0, column=1, sticky="n")

            grid = ttk.Frame(picker, padding=(8, 0, 8, 8))
            grid.grid(row=1, column=0, sticky="nsew")

            def render_month() -> None:
                for child in grid.winfo_children():
                    child.destroy()
                month_label.configure(text=f"{calendar.month_name[state['month']]} {state['year']}")
                for idx, wd in enumerate(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]):
                    ttk.Label(grid, text=wd, width=4).grid(row=0, column=idx, padx=2, pady=(0, 4))
                weeks = calendar.monthcalendar(state["year"], state["month"])
                for r, week in enumerate(weeks, start=1):
                    for c, day in enumerate(week):
                        if day == 0:
                            ttk.Label(grid, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                            continue
                        def choose(d=day):
                            share_expires_at_var.set(date(state["year"], state["month"], d).isoformat())
                            picker.destroy()
                        ttk.Button(grid, text=str(day), width=4, command=choose).grid(row=r, column=c, padx=2, pady=2)

            nav = ttk.Frame(header)
            nav.grid(row=0, column=0, sticky="w")
            def prev_month() -> None:
                if state["month"] == 1:
                    state["month"] = 12
                    state["year"] -= 1
                else:
                    state["month"] -= 1
                render_month()

            def next_month() -> None:
                if state["month"] == 12:
                    state["month"] = 1
                    state["year"] += 1
                else:
                    state["month"] += 1
                render_month()

            ttk.Button(nav, text="◀", width=3, command=prev_month).pack(side="left", padx=(0, 4))
            ttk.Button(nav, text="▶", width=3, command=next_month).pack(side="left")
            ttk.Button(header, text="Heute", command=lambda: (share_expires_at_var.set(date.today().isoformat()), picker.destroy())).grid(row=0, column=2, sticky="e")
            render_month()

        def collect_recipients() -> list[str]:
            emails: list[str] = []
            for idx in user_list.curselection():
                email = str(users[int(idx)].get("email", "") or "").strip()
                if email:
                    emails.append(email)
            selected_indices: set[int] = set(group_listbox.curselection() if group_listbox is not None else [])
            for idx, group in enumerate(groups):
                if idx not in selected_indices:
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

        def render_body_text() -> str:
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
            rendered = (body.get("1.0", "end")
                        .replace("{dokumente}", document_block)
                        .replace("{link}", document_block)
                        .replace("{datei}", doc_name)
                        .strip())
            if document_block:
                rendered += "\n\nAnlagen:\n" + document_block
            return self.normalize_mail_markup(rendered)

        def render_body_html() -> str:
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
            rendered = (body.get("1.0", "end")
                        .replace("{dokumente}", document_block)
                        .replace("{link}", document_block)
                        .replace("{datei}", doc_name)
                        .strip())
            if document_block:
                rendered += "\n\nAnlagen:\n" + document_block
            return self.render_mail_html(rendered)

        def copy_mail_text():
            recipients = collect_recipients()
            text = f"Betreff: {subject_var.get().strip()}\nEmpfänger/BCC: {'; '.join(recipients)}\nVersandart: {send_mode_var.get()}\n\n{render_body_text()}"
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
            mail_body = urllib.parse.quote(render_body_text())
            bcc = urllib.parse.quote(";".join(recipients))
            reply_to = reply_to_var.get().strip()
            if reply_to:
                url = f"mailto:?bcc={bcc}&subject={subject}&body={mail_body}%0D%0A%0D%0AAntwort%20an:%20{urllib.parse.quote(reply_to)}"
            else:
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
                "body": render_body_text(),
                "body_html": render_body_html(),
                "mode": send_mode_var.get(),
                "link": link_var.get().strip() if send_mode_var.get() == "link" else "",
                "local_file_path": first_doc if send_mode_var.get() in {"link", "attachment"} else "",
                "local_nextcloud_base": self.base_folder_var.get().strip(),
                "share_expires_at": share_expires_at_var.get().strip(),
                "document_name": Path(first_doc).name if first_doc else "",
                "reply_to": reply_to_var.get().strip(),
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
        buttons.grid(row=9, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Empfänger prüfen", command=preview_recipients).pack(side="left", padx=4)
        ttk.Button(buttons, text="Text kopieren", command=copy_mail_text).pack(side="left", padx=4)
        ttk.Button(buttons, text="Im Mailprogramm öffnen", command=open_mail_client).pack(side="left", padx=4)
        ttk.Button(buttons, text="Direkt versenden", command=send_direct).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
