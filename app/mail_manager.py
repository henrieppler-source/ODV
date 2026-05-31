from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import webbrowser

from .api_client import ApiError
from .app_logging import app_log, app_log_exception


class MailManagerMixin:
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

