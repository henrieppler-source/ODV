from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from .api_client import ApiError
from .app_logging import app_log_exception
from .config import save_config
from .database import list_history
from .file_service import load_metadata_files


class HistoryManagerMixin:
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

    def refresh_history(self) -> None:
        if not hasattr(self, "history_tree"):
            return
        scope = getattr(self, "history_scope_var", tk.StringVar(value="all")).get()
        self.config_data["history_scope"] = scope
        save_config(self.config_data)
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.history_upload_id_by_item = {}

        if self.api_token:
            try:
                response = self.api.list_documents(self.api_token, only_own=(scope == "own"))
                current_name = (self.display_name_var.get().strip() if hasattr(self, "display_name_var") else "")
                current_user_id = str((self.current_user or {}).get("id", ""))
                for doc in response.get("documents", []):
                    if scope == "own":
                        doc_user_id = str(doc.get("uploaded_by_user_id") or doc.get("user_id") or "")
                        doc_user_name = str(doc.get("uploaded_by_name") or doc.get("uploaded_by") or "")
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
                app_log_exception("Historie konnte nicht aus API geladen werden", exc)

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
        try:
            self.track_window_geometry(dialog, "Metadaten zum Historieneintrag")
        except Exception:
            pass
        dialog.transient(self)
        dialog.geometry("900x650")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        txt, frame = self.make_scrolled_text(dialog, height=25, wrap="none")
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        ttk.Button(dialog, text="Schließen", command=dialog.destroy).grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))

    def mark_history_seen(self) -> None:
        self.config_data["last_seen_history_at"] = datetime.now().isoformat(timespec="seconds")
        save_config(self.config_data)
        messagebox.showinfo("Historie", "Historie wurde als gesehen markiert. Im MVP bleibt die Tabelle trotzdem sichtbar.")
