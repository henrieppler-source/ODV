from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.parse
import webbrowser
from typing import Any

from .app_logging import app_log, app_log_exception
from . import mail_manager as mail_module
from .mail_manager_templates_utils import template_labels as _mmt_template_labels


def open_information_mail_dialog(manager: Any) -> None:
    """Rundmail erstellen und optional direkt über die Server-API versenden."""
    global tk, ttk, messagebox, filedialog
    tk = getattr(manager, "tk", mail_module.tk)
    ttk = getattr(manager, "ttk", mail_module.ttk)
    messagebox = getattr(manager, "messagebox", mail_module.messagebox)
    filedialog = getattr(manager, "filedialog", mail_module.filedialog)

    users = manager.load_email_users()
    groups = [g for g in manager.load_visible_mail_groups() if int(g.get("is_active", 1) or 0) == 1]
    is_admin = manager.is_current_admin()
    if not manager.api_token:
        messagebox.showerror("Rundmail", "Keine API-Anmeldung vorhanden. Bitte neu anmelden.")
        return

    dialog = tk.Toplevel(manager)
    dialog.title("Rundmail erstellen")
    try:
        manager.track_window_geometry(dialog, "Rundmail erstellen")
    except Exception:
        pass
    dialog.geometry("1120x820")
    dialog.transient(manager)
    dialog.columnconfigure(0, weight=0)
    dialog.columnconfigure(1, weight=1)
    dialog.rowconfigure(7, weight=1)

    ttk.Label(dialog, text="Antwort an:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
    context = manager._mail_user_context()
    current_username = context["username"] or manager.username_var.get().strip()
    current_display_name = context["display_name"] or manager.display_name_var.get().strip()
    current_email = context["email"] or manager.email_var.get().strip() or str(manager.config_data.get("current_email", "") or "")
    if not current_email and manager.api_token:
        try:
            response = manager.api.me(manager.api_token)
            user = response.get("user", {}) if isinstance(response, dict) else {}
            if isinstance(user, dict):
                manager.set_current_user(user, persist=True)
                current_username = (manager.username_var.get().strip() or str(user.get("username", "") or "").strip()).strip()
                current_display_name = ((str(user.get("display_name", "") or "").strip()) or manager.display_name_var.get().strip()).strip()
                current_email = str(user.get("email", "") or "").strip() or manager.email_var.get().strip() or str(manager.config_data.get("current_email", "") or "")
        except Exception:
            pass
    current_username_lower = current_username.lower()
    current_display_name_lower = current_display_name.lower()
    if not current_email and current_username_lower:
        current_email = next(
            (
                str(u.get("email", "") or "").strip()
                for u in users
                if str(u.get("username", "") or "").strip().lower() == current_username_lower
            ),
            "",
        )
    if not current_email and current_display_name_lower:
        current_email = next(
            (
                str(u.get("email", "") or "").strip()
                for u in users
                if str(u.get("display_name", "") or u.get("name", "") or "").strip().lower() == current_display_name_lower
            ),
            "",
        )
    reply_to_var = tk.StringVar(value=current_email)
    ttk.Entry(dialog, textvariable=reply_to_var).grid(row=0, column=1, sticky="ew", padx=10, pady=8)

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

    ttk.Label(dialog, text="Empfänger (Benutzer):").grid(row=2, column=0, sticky="nw", padx=10, pady=8)
    rec_frame = ttk.Frame(dialog)
    rec_frame.grid(row=2, column=1, sticky="nsew", padx=10, pady=8)
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

    if is_admin:
        ttk.Label(dialog, text="Weitere Empfänger:").grid(row=3, column=0, sticky="w", padx=10, pady=8)
        manual_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=manual_var).grid(row=3, column=1, sticky="ew", padx=10, pady=8)
        ttk.Label(dialog, text="E-Mail-Adressen mit Semikolon trennen. Direkter Versand erfolgt einzeln je Empfänger.", foreground="#555").grid(row=4, column=1, sticky="w", padx=10)
    else:
        manual_var = tk.StringVar(value="")

    ttk.Label(dialog, text="Betreff:").grid(row=5, column=0, sticky="w", padx=10, pady=8)
    subject_var = tk.StringVar(value="")
    ttk.Entry(dialog, textvariable=subject_var).grid(row=5, column=1, sticky="ew", padx=10, pady=8)

    send_mode_var = tk.StringVar(value="attachment")
    if is_admin:
        ttk.Label(dialog, text="Standardtext:").grid(row=6, column=0, sticky="w", padx=10, pady=8)
        template_var = tk.StringVar()
        template_names = _mmt_template_labels(manager.get_mail_text_templates())
        template_frame = ttk.Frame(dialog)
        template_frame.grid(row=6, column=1, sticky="ew", padx=10, pady=8)
        template_frame.columnconfigure(0, weight=1)
        template_combo = ttk.Combobox(template_frame, textvariable=template_var, values=template_names, state="readonly")
        template_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(template_frame, text="Laden", width=8, command=lambda: apply_selected_template()).grid(row=0, column=1, padx=(6, 0))
    else:
        template_var = tk.StringVar()
        template_combo = None

    ttk.Label(dialog, text="Text:").grid(row=7, column=0, sticky="nw", padx=10, pady=4)
    body, body_frame = manager.make_scrolled_text(dialog, height=16, wrap="word")
    body_frame.grid(row=7, column=1, sticky="nsew", padx=10, pady=4)
    body.insert("1.0", "\nViele Grüße\n" f"{(manager.current_user.get('display_name') if manager.current_user else '') or manager.display_name_var.get().strip() or 'Ortschronisten'}")

    ttk.Label(dialog, text="Dokument / Anhänge:").grid(row=8, column=0, sticky="nw", padx=10, pady=8)
    doc_path_var = tk.StringVar()
    link_var = tk.StringVar()
    selected_docs: list[str] = []
    generated_links: dict[str, str] = {}
    doc_frame = ttk.Frame(dialog)
    doc_frame.grid(row=8, column=1, sticky="ew", padx=10, pady=8)
    doc_frame.columnconfigure(1, weight=1)
    doc_frame.rowconfigure(1, weight=1)
    ttk.Button(doc_frame, text="+", width=3, command=lambda: add_doc()).grid(row=0, column=0, padx=(0, 6), sticky="w")
    ttk.Entry(doc_frame, textvariable=doc_path_var).grid(row=0, column=1, sticky="ew")
    ttk.Button(doc_frame, text="Entfernen", command=lambda: remove_selected_doc()).grid(row=0, column=2, padx=(6, 0))
    ttk.Button(doc_frame, text="Leeren", command=lambda: clear_docs()).grid(row=0, column=3, padx=(6, 0))
    doc_list = tk.Listbox(doc_frame, height=4, exportselection=False)
    doc_list.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(6, 0))
    doc_scroll = ttk.Scrollbar(doc_frame, orient="vertical", command=doc_list.yview)
    doc_list.configure(yscrollcommand=doc_scroll.set)
    doc_scroll.grid(row=1, column=4, sticky="ns", pady=(6, 0))
    ttk.Label(
        doc_frame,
        text="Mit + können Dokumente nacheinander hinzugefügt werden. Nextcloud-Dateien werden bei Downloadlink als Link versendet, andere Dateien immer als normale Anlage.",
        foreground="#555",
    ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(4, 0))

    ttk.Label(dialog, text="Versandart Anlagen:").grid(row=9, column=0, sticky="w", padx=10, pady=8)
    mode_frame = ttk.Frame(dialog)
    mode_frame.grid(row=9, column=1, sticky="w", padx=10, pady=8)
    ttk.Radiobutton(mode_frame, text="Nextcloud-Downloadlink versenden", variable=send_mode_var, value="link").pack(side="left", padx=(0, 18))
    ttk.Radiobutton(mode_frame, text="Dokument anhängen", variable=send_mode_var, value="attachment").pack(side="left")

    ttk.Label(dialog, text="Dokumentenliste:").grid(row=10, column=0, sticky="nw", padx=10, pady=4)
    link_frame = ttk.Frame(dialog)
    link_frame.grid(row=10, column=1, sticky="ew", padx=10, pady=4)
    link_frame.columnconfigure(0, weight=1)
    link_text, link_text_frame = manager.make_scrolled_text(link_frame, height=5, wrap="word")
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
        expiry = share_expires_at_var.get().strip()
        current_mode = send_mode_var.get()
        nextcloud_docs = [path for path in selected_docs if manager.is_path_under_nextcloud_base(path)]
        if current_mode == "link" and not nextcloud_docs:
            current_mode = "attachment"
        if current_mode == "link" and expiry and nextcloud_docs:
            parts.append(f"Gültig bis: {expiry}")
            parts.append("")
        for path in selected_docs:
            name = Path(path).name
            link = generated_links.get(path, "")
            if current_mode == "link" and manager.is_path_under_nextcloud_base(path):
                if force_links or not link:
                    link = manager.nextcloud_web_link_for_local_path(path, share_expires_at_var.get().strip())
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

    def effective_send_mode() -> str:
        if not selected_docs:
            return "none"
        if send_mode_var.get() == "link" and any(manager.is_path_under_nextcloud_base(path) for path in selected_docs):
            return "link"
        return "attachment"

    def apply_selected_template() -> None:
        label = template_var.get().strip()
        if not label:
            return
        for item in manager.get_mail_text_templates():
            if item.get("label", "") == label:
                body.delete("1.0", "end")
                body.insert("1.0", item.get("text", ""))
                refresh_document_block(force_links=False)
                return

    if template_combo is not None:
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

    ttk.Label(dialog, text="Verfallsdatum:").grid(row=11, column=0, sticky="w", padx=10, pady=8)
    share_expires_at_var = tk.StringVar(value=(date.today() + timedelta(days=14)).isoformat())
    expiry_frame = ttk.Frame(dialog)
    expiry_frame.grid(row=11, column=1, sticky="w", padx=10, pady=8)
    expiry_entry = ttk.Entry(expiry_frame, textvariable=share_expires_at_var, width=16)
    expiry_entry.pack(side="left")
    ttk.Button(expiry_frame, text="Kalender", width=9, command=lambda: open_date_picker()).pack(side="left", padx=(4, 0))
    ttk.Button(expiry_frame, text="Heute", width=7, command=lambda: share_expires_at_var.set(date.today().isoformat())).pack(side="left", padx=(4, 0))

    def collect_recipients() -> list[str]:
        return manager.collect_mail_recipients(users, user_list, groups, group_listbox, manual_var.get())

    def build_document_payload_for_body() -> tuple[str, str]:
        if selected_docs:
            doc_name = ", ".join(Path(x).name for x in selected_docs)
        else:
            doc_name = Path(doc_path_var.get()).name if doc_path_var.get().strip() else ""

        current_mode = effective_send_mode()
        if current_mode == "none":
            return "", ""

        document_block = link_var.get().strip()
        if selected_docs and current_mode == "link" and not document_block:
            document_block = build_documents_block(force_links=True)
        elif selected_docs and current_mode == "attachment" and not document_block:
            document_block = "\n".join(f"Datei: {Path(x).name}" for x in selected_docs)

        return doc_name, document_block

    def render_body_text() -> str:
        doc_name, document_block = build_document_payload_for_body()
        rendered = (body.get("1.0", "end")
                    .replace("{dokumente}", document_block)
                    .replace("{link}", document_block)
                    .replace("{datei}", doc_name)
                    .strip())
        if document_block:
            rendered += "\n\nAnlagen:\n" + document_block
        return manager.normalize_mail_markup(rendered)

    def render_body_html() -> str:
        doc_name, document_block = build_document_payload_for_body()
        rendered = (body.get("1.0", "end")
                    .replace("{dokumente}", document_block)
                    .replace("{link}", document_block)
                    .replace("{datei}", doc_name)
                    .strip())
        if document_block:
            rendered += "\n\nAnlagen:\n" + document_block
        return manager.render_mail_html(rendered)

    def copy_mail_text():
        recipients = collect_recipients()
        text = f"Betreff: {subject_var.get().strip()}\nEmpfänger/BCC: {'; '.join(recipients)}\nVersandart Anlagen: {send_mode_var.get()}\n\n{render_body_text()}"
        dialog.clipboard_clear()
        dialog.clipboard_append(text)
        messagebox.showinfo("Kopiert", f"Der E-Mail-Text wurde in die Zwischenablage kopiert.\nEmpfänger: {len(recipients)}", parent=dialog)

    def open_mail_client():
        recipients = collect_recipients()
        if not recipients:
            messagebox.showwarning("Rundmail", "Bitte mindestens einen Empfänger auswählen oder manuell eintragen.", parent=dialog)
            return
        current_mode = effective_send_mode()
        has_local_attachments = any(not manager.is_path_under_nextcloud_base(path) for path in selected_docs)
        if selected_docs and (current_mode == "attachment" or has_local_attachments):
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
        selected_mode = effective_send_mode()
        nc_docs = [path for path in selected_docs if manager.is_path_under_nextcloud_base(path)]
        local_docs = [path for path in selected_docs if not manager.is_path_under_nextcloud_base(path)]
        first_nc_doc = nc_docs[0] if nc_docs else ""
        first_doc = first_nc_doc or (selected_docs[0] if selected_docs else doc_path_var.get().strip())
        payload_mode = selected_mode
        if payload_mode == "link" and not first_nc_doc and selected_docs:
            payload_mode = "attachment"
        if payload_mode == "link" and first_nc_doc:
            try:
                refresh_document_block(force_links=True)
            except Exception as exc:
                messagebox.showerror("Nextcloud-Link", f"Der Downloadlink konnte nicht erstellt werden:\n{exc}", parent=dialog)
                return
            missing_links = [path for path in nc_docs if not generated_links.get(path, "").strip()]
            if missing_links:
                messagebox.showerror(
                    "Nextcloud-Link",
                    "Der öffentliche Downloadlink konnte nicht erstellt werden.\n"
                    "Bitte Nextcloud-Zugangsdaten prüfen oder als Anlage versenden.",
                    parent=dialog,
                )
                return
        if not selected_docs and not doc_path_var.get().strip():
            payload_mode = "none"
        payload = {
            "recipients": recipients,
            "subject": subject,
            "body": render_body_text(),
            "body_html": render_body_html(),
            "mode": payload_mode,
            "link": link_var.get().strip() if payload_mode == "link" else "",
            "local_file_path": first_nc_doc if payload_mode == "link" else "",
            "local_nextcloud_base": manager.base_folder_var.get().strip(),
            "share_expires_at": share_expires_at_var.get().strip(),
            "document_name": Path(first_doc).name if first_doc else "",
            "reply_to": reply_to_var.get().strip(),
        }

        files_for_attachment: list[str] = []
        if payload_mode == "attachment":
            files_for_attachment = selected_docs if selected_docs else ([doc_path_var.get().strip()] if doc_path_var.get().strip() else [])
        elif payload_mode == "link":
            files_for_attachment = local_docs
        if payload_mode == "attachment" and not files_for_attachment:
            messagebox.showerror("Anlage", "Bitte mindestens eine Datei als Anlage auswählen.", parent=dialog)
            return
        if payload_mode == "none":
            payload["link"] = ""
            payload["local_file_path"] = ""
            payload["document_name"] = ""
        if payload_mode == "attachment":
            try:
                attachments = manager.build_mail_attachments(files_for_attachment)
                payload["attachments"] = attachments
                payload["attachment"] = attachments[0]
            except Exception as exc:
                messagebox.showerror("Anlage", str(exc), parent=dialog)
                return
        elif payload_mode == "link" and files_for_attachment:
            try:
                attachments = manager.build_mail_attachments(files_for_attachment)
                payload["attachments"] = attachments
                payload["attachment"] = attachments[0]
            except Exception as exc:
                messagebox.showerror("Anlage", str(exc), parent=dialog)
                return
        if not messagebox.askyesno("Rundmail senden", f"Rundmail jetzt an {len(recipients)} Empfänger senden?", parent=dialog):
            return
        try:
            response = manager.api.send_mail(manager.api_token, payload)
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
        if send_mode_var.get() in {"attachment", "link"}:
            refresh_document_block(force_links=False)
        elif send_mode_var.get() == "none":
            link_var.set("")
            link_text.delete("1.0", "end")

    send_mode_var.trace_add("write", on_send_mode_changed)

    buttons = ttk.Frame(dialog)
    buttons.grid(row=12, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
    ttk.Button(buttons, text="Empfänger prüfen", command=preview_recipients).pack(side="left", padx=4)
    ttk.Button(buttons, text="Text kopieren", command=copy_mail_text).pack(side="left", padx=4)
    ttk.Button(buttons, text="Im Mailprogramm öffnen", command=open_mail_client).pack(side="left", padx=4)
    ttk.Button(buttons, text="Direkt versenden", command=send_direct).pack(side="left", padx=4)
    ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
