from __future__ import annotations

import ftplib
import posixpath
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from .app_logging import app_log_exception
from .config import save_config
from .database import add_history
from .models import HistoryEntry
from .secure_store import SecureStoreError, protect_text, unprotect_text


class AdminUiManagerMixin:
    def create_admin_tab(self) -> None:
        self.admin_tab.columnconfigure(0, weight=1)
        self.admin_tab.rowconfigure(0, weight=1)

        self.admin_outer_pane = ttk.PanedWindow(self.admin_tab, orient=tk.HORIZONTAL)
        self.admin_outer_pane.grid(row=0, column=0, sticky="nsew")
        self.admin_outer_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())

        list_frame = ttk.LabelFrame(self.admin_outer_pane, text="Uploads / Dateien", padding=8)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        filter_frame = ttk.Frame(list_frame)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(filter_frame, text="Status:").pack(side="left")
        self.admin_status_var = tk.StringVar(value="alle")
        self.admin_status_combo = ttk.Combobox(filter_frame, textvariable=self.admin_status_var, values=["alle", "hochgeladen", "rueckfrage", "geprueft", "uebernommen", "archiviert"], width=18, state="readonly")
        self.admin_status_combo.pack(side="left", padx=4)
        self.admin_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_admin_uploads(show_message=False))
        self.merge_pdfs_top_button = ttk.Button(filter_frame, text="Ausgewählte PDFs zusammenfassen...", command=self.merge_selected_admin_pdfs)
        self.merge_pdfs_top_button.pack(side="left", padx=(16, 0))

        self.admin_tree = ttk.Treeview(
            list_frame,
            columns=("upload_id", "status", "filename", "by", "date", "type"),
            show="headings",
            selectmode="extended",
        )
        for col, label, width in [
            ("upload_id", "Upload-ID", 155),
            ("status", "Status", 100),
            ("filename", "Datei", 270),
            ("by", "Erfasst von", 160),
            ("date", "Datum", 150),
            ("type", "Typ", 130),
        ]:
            self.admin_tree.heading(col, text=label, anchor="w")
            self.admin_tree.column(col, width=width, anchor="w")
        self.admin_tree.grid(row=1, column=0, sticky="nsew")
        self.admin_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_selected_admin_details())
        self.admin_tree.bind("<Double-1>", lambda _e: self.open_selected_admin_file())
        self.admin_tree.bind("<Button-3>", self.show_admin_tree_context_menu)
        admin_vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.admin_tree.yview)
        admin_hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.admin_tree.xview)
        self.admin_tree.configure(yscrollcommand=admin_vsb.set, xscrollcommand=admin_hsb.set)
        admin_vsb.grid(row=1, column=1, sticky="ns")
        admin_hsb.grid(row=2, column=0, sticky="ew")

        actions = ttk.LabelFrame(list_frame, text="Admin-Aktionen", padding=8)
        self.admin_actions_frame = actions
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(1, weight=1)
        self.new_status_label = ttk.Label(actions, text="Dokumentstatus:")
        self.new_status_label.grid(row=0, column=0, sticky="w")
        self.new_status_var = tk.StringVar(value="rueckfrage")
        self.new_status_combo = ttk.Combobox(actions, textvariable=self.new_status_var, values=["hochgeladen", "rueckfrage", "geprueft", "uebernommen", "archiviert"], width=18, state="readonly")
        self.new_status_combo.grid(row=0, column=1, sticky="w", padx=6)
        self.new_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.admin_set_status(silent=True))

        self.admin_destination_label = ttk.Label(actions, text="Datei ablegen in:")
        self.admin_destination_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.admin_destination_var = tk.StringVar()
        self.admin_destination_combo = ttk.Combobox(actions, textvariable=self.admin_destination_var, state="readonly")
        self.admin_destination_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.admin_destination_tree_button = ttk.Button(actions, text="Baum...", command=self.choose_admin_destination)
        self.admin_destination_tree_button.grid(row=1, column=2, sticky="e", padx=6, pady=(6, 0))

        ttk.Label(actions, text="Neuer Dateiname:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.admin_new_filename_var = tk.StringVar()
        ttk.Entry(actions, textvariable=self.admin_new_filename_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.admin_rename_button = ttk.Button(actions, text="Datei umbenennen / verschieben", command=self.admin_rename_or_move)
        self.admin_rename_button.grid(row=2, column=2, sticky="e", padx=6, pady=(6, 0))
        points_frame = ttk.Frame(actions)
        points_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Label(points_frame, text="Punkte Dokument:").pack(side="left")
        self.admin_document_points_var = tk.StringVar(value="keine Datei ausgewählt")
        ttk.Label(points_frame, textvariable=self.admin_document_points_var).pack(side="left", padx=(6, 18))
        self.manual_points_button = ttk.Button(points_frame, text="Sonderpunkte erfassen...", command=self.open_manual_points_dialog)
        self.manual_points_button.pack(side="left", padx=(0, 8))
        self.point_details_button = ttk.Button(points_frame, text="Punktdetails...", command=self.open_document_points_detail_dialog)
        self.point_details_button.pack(side="left")

        self.admin_right_pane = ttk.PanedWindow(self.admin_outer_pane, orient=tk.VERTICAL)
        self.admin_right_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())
        self.admin_outer_pane.add(list_frame, weight=1)
        self.admin_outer_pane.add(self.admin_right_pane, weight=2)
        self.configure_admin_actions_for_role()

        admin_preview_frame = ttk.LabelFrame(self.admin_right_pane, text="Vorschau / Personen", padding=8)
        self.admin_preview_frame = admin_preview_frame
        admin_preview_frame.columnconfigure(0, weight=0)
        admin_preview_frame.columnconfigure(1, weight=1)
        admin_preview_frame.rowconfigure(1, weight=1)
        self.admin_show_persons_var = tk.BooleanVar(value=True)
        self.admin_show_persons_check = ttk.Checkbutton(admin_preview_frame, text="Personen anzeigen", variable=self.admin_show_persons_var, command=lambda: self.show_admin_preview(self.selected_admin_upload() or {}))
        self.admin_show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.admin_show_persons_check.grid_remove()
        self.admin_person_legend_text, admin_legend_frame = self.make_scrolled_text(admin_preview_frame, height=7, wrap="word")
        self.admin_person_legend_frame = admin_legend_frame
        admin_legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.admin_person_legend_text.configure(width=30, state="disabled")
        self.admin_preview_label = ttk.Label(admin_preview_frame, text="Keine Datei ausgewählt.", anchor="center")
        self.admin_preview_label.grid(row=1, column=1, sticky="nsew")
        self.admin_preview_label.bind("<Double-1>", lambda _e: self.edit_persons_for_admin_file())
        self.admin_preview_image = None

        detail_outer = ttk.LabelFrame(self.admin_right_pane, text="Metadaten bearbeiten", padding=8)
        detail_outer.columnconfigure(0, weight=1)
        detail_outer.rowconfigure(0, weight=1)
        detail_canvas = tk.Canvas(detail_outer, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(detail_outer, orient="vertical", command=detail_canvas.yview)
        detail_frame = ttk.Frame(detail_canvas)
        detail_window = detail_canvas.create_window((0, 0), window=detail_frame, anchor="nw")
        detail_frame.bind("<Configure>", lambda _e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))
        detail_canvas.bind("<Configure>", lambda e: detail_canvas.itemconfigure(detail_window, width=e.width))
        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_canvas.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")

        form = self.create_metadata_form_two_columns(detail_frame, "admin")
        self.admin_meta_vars = form["vars"]  # type: ignore[assignment]
        self.admin_meta_widgets = form.get("widgets", [])  # type: ignore[assignment]
        self.admin_description_text = form["description_text"]  # type: ignore[assignment]
        self.admin_description_counter_var = form.get("description_counter_var")  # type: ignore[assignment]
        self.admin_note_text = form["note_text"]  # type: ignore[assignment]
        self.admin_json_text = form["json_text"]  # type: ignore[assignment]
        self.refresh_admin_uploaded_by_options()

        self.admin_right_pane.add(admin_preview_frame, weight=1)
        self.admin_right_pane.add(detail_outer, weight=3)
        self.refresh_admin_destination_choices()
        self.after(200, self.restore_pane_positions)

    def open_admin_settings_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Admin-Einstellungen sind nur für Superadmins sichtbar.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Admin-Einstellungen")
        try: self.track_window_geometry(dialog, "Admin-Einstellungen")
        except Exception: pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("920x720")
        dialog.minsize(880, 640)
        dialog.resizable(True, True)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Admin-Einstellungen", font=("", 12, "bold")).grid(row=0, column=0, sticky="w")

        dirty_var = tk.BooleanVar(value=False)
        saving_var = tk.BooleanVar(value=False)

        def mark_dirty(*_args) -> None:
            if not saving_var.get():
                dirty_var.set(True)

        notebook = ttk.Notebook(dialog)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        general_tab = ttk.Frame(notebook, padding=12)
        api_tab = ttk.Frame(notebook, padding=12)
        ftp_tab = ttk.Frame(notebook, padding=12)
        links_tab = ttk.Frame(notebook, padding=12)
        notebook.add(general_tab, text="Allgemein")
        notebook.add(api_tab, text="API / OpenAI")
        notebook.add(ftp_tab, text="FTP-Deployment")
        notebook.add(links_tab, text="Links / Hinweise")
        for tab in (general_tab, api_tab, ftp_tab, links_tab):
            tab.columnconfigure(1, weight=1)

        ttk.Label(general_tab, text="Metadaten und Arbeitsordner", font=("", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(general_tab, text="Metadatenordner unter Nextcloud-Stammverzeichnis:").grid(row=1, column=0, sticky="w", pady=6)
        folder_name_var = tk.StringVar(value=self.config_data.get("metadata_folder_name", ".ortschronik_metadaten"))
        ttk.Entry(general_tab, textvariable=folder_name_var, width=42).grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(general_tab, text="Beispiel: .ortschronik_metadaten").grid(row=1, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(general_tab, text="Aktueller vollständiger Metadatenpfad:").grid(row=2, column=0, sticky="w", pady=6)
        meta_preview_var = tk.StringVar(value=self.metadata_folder_var.get())
        ttk.Label(general_tab, textvariable=meta_preview_var).grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Label(general_tab, text="Ordner, die Admins bearbeiten dürfen:").grid(row=3, column=0, sticky="nw", pady=(10, 6))
        work_text = tk.Text(general_tab, height=8, width=55)
        work_text.grid(row=3, column=1, columnspan=2, sticky="nsew", padx=6, pady=(10, 6))
        work_text.insert("1.0", "\n".join(sorted(self.admin_work_folder_names)))
        work_text.bind("<<Modified>>", lambda _event: (work_text.edit_modified(False), mark_dirty()))
        general_tab.rowconfigure(3, weight=1)
        ttk.Label(general_tab, text="Ein Ordnername pro Zeile. Es reicht der Ordnername, z. B. 01_ABLAGE_ORTSCHRONIK.", wraplength=620).grid(row=4, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 10))

        ttk.Label(api_tab, text="Server / API", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(api_tab, text="API-URL:").grid(row=1, column=0, sticky="w", pady=4)
        api_url_var = tk.StringVar(value=self.config_data.get("api_url", "https://ortschronik.info/api"))
        ttk.Entry(api_tab, textvariable=api_url_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        ttk.Label(api_tab, text="MySQL-Host:").grid(row=2, column=0, sticky="w", pady=4)
        mysql_host_var = tk.StringVar(value=self.config_data.get("mysql_host", "https://ortschronik.info"))
        ttk.Entry(api_tab, textvariable=mysql_host_var).grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="Port:").grid(row=2, column=2, sticky="w", padx=6, pady=4)
        mysql_port_var = tk.StringVar(value=self.config_data.get("mysql_port", "3306"))
        ttk.Entry(api_tab, textvariable=mysql_port_var, width=8).grid(row=2, column=3, sticky="w", padx=6, pady=4)
        ttk.Label(api_tab, text="Datenbank:").grid(row=3, column=0, sticky="w", pady=4)
        mysql_database_var = tk.StringVar(value=self.config_data.get("mysql_database", "d047179a"))
        ttk.Entry(api_tab, textvariable=mysql_database_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="Datenbank-Benutzer:").grid(row=4, column=0, sticky="w", pady=4)
        mysql_user_var = tk.StringVar(value=self.config_data.get("mysql_user", "d047179a"))
        ttk.Entry(api_tab, textvariable=mysql_user_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        ttk.Separator(api_tab).grid(row=5, column=0, columnspan=4, sticky="ew", pady=(12, 10))
        ttk.Label(api_tab, text="OpenAI", font=("", 10, "bold")).grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(api_tab, text="OpenAI API-Schlüssel:").grid(row=7, column=0, sticky="w", pady=4)
        openai_key_var = tk.StringVar(value=self.config_data.get("openai_api_key", ""))
        ttk.Entry(api_tab, textvariable=openai_key_var, width=42, show="*").grid(row=7, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(api_tab, text="OpenAI-Modell:").grid(row=8, column=0, sticky="w", pady=4)
        openai_model_var = tk.StringVar(value=self.config_data.get("openai_model", "gpt-3.5-turbo"))
        openai_model_values = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        if openai_model_var.get().strip() and openai_model_var.get().strip() not in openai_model_values:
            openai_model_values.append(openai_model_var.get().strip())
        ttk.Combobox(api_tab, textvariable=openai_model_var, values=openai_model_values, state="readonly").grid(row=8, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        openai_pdf_pages_var = tk.StringVar(value=str(self.config_data.get("openai_pdf_sample_pages", 10) or 10))
        openai_text_chars_var = tk.StringVar(value=str(self.config_data.get("openai_text_sample_chars", 4000) or 4000))
        openai_points_var = tk.StringVar(value=str(self.config_data.get("openai_metadata_points", 1) or 1))
        ttk.Label(api_tab, text="OpenAI-Auszug:").grid(row=9, column=0, sticky="w", pady=4)
        openai_limits_frame = ttk.Frame(api_tab)
        openai_limits_frame.grid(row=9, column=1, columnspan=3, sticky="w", padx=6, pady=4)
        ttk.Label(openai_limits_frame, text="PDF-Seiten").pack(side="left")
        ttk.Spinbox(openai_limits_frame, from_=1, to=100, textvariable=openai_pdf_pages_var, width=6).pack(side="left", padx=(6, 16))
        ttk.Label(openai_limits_frame, text="max. Zeichen").pack(side="left")
        ttk.Spinbox(openai_limits_frame, from_=500, to=100000, increment=500, textvariable=openai_text_chars_var, width=8).pack(side="left", padx=(6, 16))

        def reset_openai_limits() -> None:
            openai_pdf_pages_var.set("10")
            openai_text_chars_var.set("4000")
            openai_points_var.set("1")

        ttk.Button(openai_limits_frame, text="Standard", command=reset_openai_limits).pack(side="left")
        ttk.Label(openai_limits_frame, text="OpenAI-Punkte je Feld").pack(side="left", padx=(16, 0))
        ttk.Spinbox(openai_limits_frame, from_=0, to=50, textvariable=openai_points_var, width=6).pack(side="left", padx=(6, 0))
        ttk.Label(api_tab, text="Empfohlen: gpt-4o-mini. Für PDFs werden standardmäßig nur die ersten 10 Seiten und maximal 4000 Zeichen an OpenAI gegeben. OpenAI-Punkte werden je Metadatenfeld in der Punkteverwaltung gepflegt.", wraplength=760).grid(row=10, column=0, columnspan=4, sticky="w", pady=(0, 8))

        openai_test_status_var = tk.StringVar(value="OpenAI-Schlüssel nicht geprüft")
        openai_balance_var = tk.StringVar(value="Guthaben: n.v.")

        def load_openai_points_rule() -> None:
            if not self.api_token:
                return
            def run_load() -> None:
                try:
                    resp = self.api.list_point_rules(self.api_token, self._current_points_year())
                    for rule in resp.get("rules", []) or []:
                        if str(rule.get("evaluation_source", "")) == "openAI":
                            self.after(0, lambda value=str(int(rule.get("points", 1) or 0)): openai_points_var.set(value))
                            break
                except Exception:
                    pass
            threading.Thread(target=run_load, daemon=True).start()

        load_openai_points_rule()

        def check_openai_key() -> None:
            openai_test_status_var.set("OpenAI prüft …")
            openai_balance_var.set("Guthaben: n.v.")
            def run_check() -> None:
                try:
                    client = OpenAIClient(openai_key_var.get().strip(), openai_model_var.get().strip() or "gpt-3.5-turbo")
                    client.verify_key()
                    balance = client.get_balance()
                    available = balance.get("available")
                    if isinstance(available, (int, float)):
                        balance_text = f"Guthaben: {available:.2f} USD"
                    else:
                        balance_text = "Guthaben: k.A."
                    self.after(0, lambda: openai_test_status_var.set("OpenAI: Schlüssel OK"))
                    self.after(0, lambda: openai_balance_var.set(balance_text))
                except OpenAIError as exc:
                    self.after(0, lambda: openai_test_status_var.set(f"OpenAI: {exc.user_message()}"))
                    self.after(0, lambda: openai_balance_var.set("Guthaben: k.A."))
                except Exception:
                    self.after(0, lambda: openai_test_status_var.set("OpenAI-Prüfung fehlgeschlagen"))
                    self.after(0, lambda: openai_balance_var.set("Guthaben: k.A."))
            threading.Thread(target=run_check, daemon=True).start()

        openai_actions = ttk.Frame(api_tab)
        openai_actions.grid(row=11, column=0, columnspan=4, sticky="ew", pady=4)
        ttk.Button(openai_actions, text="OpenAI-Schlüssel prüfen", command=check_openai_key).pack(side="left")
        ttk.Label(openai_actions, textvariable=openai_test_status_var, wraplength=520, foreground="#555555").pack(side="left", padx=(12, 0))
        ttk.Label(api_tab, textvariable=openai_balance_var, wraplength=520, foreground="#555555").grid(row=12, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 4))

        ttk.Label(ftp_tab, text="FTP-Deployment", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(ftp_tab, text="FTP-Server:").grid(row=1, column=0, sticky="w", pady=4)
        ftp_host_var = tk.StringVar(value=self.config_data.get("ftp_host", "w0210fa6.kasserver.com"))
        ttk.Entry(ftp_tab, textvariable=ftp_host_var).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="Port:").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        ftp_port_var = tk.StringVar(value=self.config_data.get("ftp_port", "21"))
        ttk.Entry(ftp_tab, textvariable=ftp_port_var, width=8).grid(row=1, column=3, sticky="w", padx=6, pady=4)
        ttk.Label(ftp_tab, text="FTP-Benutzer:").grid(row=2, column=0, sticky="w", pady=4)
        ftp_user_var = tk.StringVar(value=self.config_data.get("ftp_user", "f0185adc"))
        ttk.Entry(ftp_tab, textvariable=ftp_user_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="FTP-Passwort:").grid(row=3, column=0, sticky="w", pady=4)
        ftp_password_var = tk.StringVar(value="")
        ttk.Entry(ftp_tab, textvariable=ftp_password_var, show="*").grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ftp_saved = bool(str(self.config_data.get("ftp_password_dpapi", "") or "").strip())
        ftp_status_var = tk.StringVar(value="FTP-Passwort ist verschlüsselt gespeichert." if ftp_saved else "FTP-Passwort noch nicht gespeichert.")
        ttk.Label(ftp_tab, text="Leer lassen, um ein bereits gespeichertes Passwort zu behalten.", wraplength=720).grid(row=4, column=1, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        ttk.Label(ftp_tab, text="Lokale routes.php:").grid(row=5, column=0, sticky="w", pady=4)
        ftp_local_routes_path_var = tk.StringVar(value=self.config_data.get("ftp_local_routes_path", "server/routes.php"))
        ttk.Entry(ftp_tab, textvariable=ftp_local_routes_path_var).grid(row=5, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(ftp_tab, text="Zielpfad routes.php:").grid(row=6, column=0, sticky="w", pady=4)
        ftp_routes_path_var = tk.StringVar(value=self.config_data.get("ftp_remote_routes_path", "/ortschronik.info/ortschronik-api/routes.php"))
        ttk.Entry(ftp_tab, textvariable=ftp_routes_path_var).grid(row=6, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        def current_ftp_password() -> str:
            password = ftp_password_var.get()
            if password:
                return password
            encrypted = str(self.config_data.get("ftp_password_dpapi", "") or "")
            if not encrypted:
                return ""
            return unprotect_text(encrypted)

        def check_ftp_connection() -> None:
            ftp_status_var.set("FTP prüft ...")

            def run_check() -> None:
                try:
                    host = ftp_host_var.get().strip()
                    user = ftp_user_var.get().strip()
                    port = int(ftp_port_var.get().strip() or "21")
                    password = current_ftp_password()
                    if not host or not user or not password:
                        raise SecureStoreError("Bitte FTP-Server, Benutzer und Passwort erfassen.")
                    target_dir = posixpath.dirname(ftp_routes_path_var.get().strip())
                    with ftplib.FTP() as ftp:
                        ftp.connect(host, port, timeout=20)
                        ftp.login(user, password)
                        if target_dir and target_dir != ".":
                            ftp.cwd(target_dir)
                    self.after(0, lambda: ftp_status_var.set("FTP: Verbindung OK"))
                except Exception as exc:
                    self.after(0, lambda: ftp_status_var.set(f"FTP: {exc}"))

            threading.Thread(target=run_check, daemon=True).start()

        ftp_buttons = ttk.Frame(ftp_tab)
        ftp_buttons.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(8, 8))
        ttk.Button(ftp_buttons, text="FTP-Verbindung prüfen", command=check_ftp_connection).pack(side="left")
        ttk.Label(ftp_buttons, textvariable=ftp_status_var, foreground="#555555", wraplength=620).pack(side="left", padx=(12, 0))

        ttk.Label(links_tab, text="Nextcloud und Hinweise", font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(links_tab, text="Nextcloud Web-Dateiansicht:").grid(row=1, column=0, sticky="w", pady=4)
        nc_web_var = tk.StringVar(value=self.config_data.get("nextcloud_web_files_url", "https://nx94165.your-storageshare.de/apps/files/files"))
        ttk.Entry(links_tab, textvariable=nc_web_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(links_tab, text="Beispiel: https://nx94165.your-storageshare.de/apps/files/files  ·  Links zeigen auf den betreffenden Nextcloud-Ordner.", wraplength=760).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 10))
        ttk.Label(links_tab, text="Das Datenbankpasswort und SMTP-Passwort liegen nur auf dem Server/API. Das FTP-Passwort wird lokal per Windows-DPAPI verschlüsselt. Die OpenAI-Punkte je Metadatenfeld ändern Sie unter Admin > Punkteregeln verwalten.", wraplength=760).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 10))

        tracked_vars = [
            folder_name_var, api_url_var, openai_key_var, openai_model_var,
            openai_pdf_pages_var, openai_text_chars_var, openai_points_var,
            mysql_host_var, mysql_port_var, mysql_database_var, mysql_user_var,
            ftp_host_var, ftp_port_var, ftp_user_var, ftp_password_var,
            ftp_local_routes_path_var, ftp_routes_path_var, nc_web_var,
        ]
        for var in tracked_vars:
            var.trace_add("write", mark_dirty)

        def update_preview(*_):
            old = self.config_data.get("metadata_folder_name", ".ortschronik_metadaten")
            self.config_data["metadata_folder_name"] = folder_name_var.get().strip() or ".ortschronik_metadaten"
            self.ensure_standard_metadata_folder()
            meta_preview_var.set(self.metadata_folder_var.get())
            self.config_data["metadata_folder_name"] = old
            self.ensure_standard_metadata_folder()
        folder_name_var.trace_add("write", update_preview)

        def save_settings(close_after: bool = True) -> bool:
            saving_var.set(True)
            name = folder_name_var.get().strip() or ".ortschronik_metadaten"
            if not name.startswith("."):
                name = "." + name
            folders = [line.strip() for line in work_text.get("1.0", "end").splitlines() if line.strip()]
            if not folders:
                messagebox.showwarning("Admin-Ordner", "Bitte mindestens einen Admin-Bearbeitungsordner erfassen.", parent=dialog)
                saving_var.set(False)
                return False
            try:
                openai_pdf_pages = max(1, min(100, int(openai_pdf_pages_var.get())))
                openai_text_chars = max(500, min(100000, int(openai_text_chars_var.get())))
                openai_points = max(0, min(50, int(openai_points_var.get())))
            except ValueError:
                messagebox.showwarning("OpenAI-Auszug", "Bitte gültige Zahlen für Seiten, Zeichen und OpenAI-Punkte erfassen.", parent=dialog)
                saving_var.set(False)
                return False
            self.config_data["metadata_folder_name"] = name
            self.admin_work_folder_names = set(folders)
            self.config_data["admin_work_folder_names"] = sorted(self.admin_work_folder_names)
            self.config_data["api_url"] = api_url_var.get().strip()
            self.config_data["openai_api_key"] = openai_key_var.get().strip()
            self.config_data["openai_model"] = openai_model_var.get().strip() or "gpt-3.5-turbo"
            self.config_data["openai_pdf_sample_pages"] = openai_pdf_pages
            self.config_data["openai_text_sample_chars"] = openai_text_chars
            self.config_data["openai_metadata_points"] = openai_points
            self.config_data["mysql_host"] = mysql_host_var.get().strip()
            self.config_data["mysql_port"] = mysql_port_var.get().strip() or "3306"
            self.config_data["mysql_database"] = mysql_database_var.get().strip()
            self.config_data["mysql_user"] = mysql_user_var.get().strip()
            self.config_data["ftp_host"] = ftp_host_var.get().strip()
            self.config_data["ftp_port"] = ftp_port_var.get().strip() or "21"
            self.config_data["ftp_user"] = ftp_user_var.get().strip()
            self.config_data["ftp_local_routes_path"] = ftp_local_routes_path_var.get().strip() or "server/routes.php"
            self.config_data["ftp_remote_routes_path"] = ftp_routes_path_var.get().strip()
            if ftp_password_var.get():
                try:
                    self.config_data["ftp_password_dpapi"] = protect_text(ftp_password_var.get())
                except SecureStoreError as exc:
                    messagebox.showwarning("FTP-Passwort", str(exc), parent=dialog)
                    saving_var.set(False)
                    return False
            self.config_data["nextcloud_web_files_url"] = nc_web_var.get().strip()
            self.ensure_standard_metadata_folder()
            save_config(self.config_data)
            # OpenAI-Punkte werden feldbezogen in der Punkteverwaltung gepflegt.
            add_history(HistoryEntry.now(self.display_name_var.get().strip() or "Superadmin", "Admin-Einstellungen geändert", f"Metadatenordner={name}; Admin-Ordner={', '.join(folders)}"))
            self.refresh_history()
            self.refresh_admin_uploads(show_message=False)
            dirty_var.set(False)
            saving_var.set(False)
            messagebox.showinfo("Admin-Einstellungen", "Einstellungen wurden gespeichert.", parent=dialog)
            if close_after:
                dialog.destroy()
            return True

        def close_dialog() -> None:
            if not dirty_var.get():
                dialog.destroy()
                return
            answer = messagebox.askyesnocancel(
                "Änderungen speichern?",
                "Es gibt ungespeicherte Änderungen in den Admin-Einstellungen.\n\nSollen sie vor dem Schließen gespeichert werden?",
                parent=dialog,
            )
            if answer is None:
                return
            if answer:
                save_settings(close_after=True)
                return
            dialog.destroy()

        buttons = ttk.Frame(header)
        buttons.grid(row=0, column=1, sticky="e")
        ttk.Button(buttons, text="Speichern", command=lambda: save_settings(close_after=False)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Schließen", command=close_dialog).pack(side="left", padx=6)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dirty_var.set(False)

    # Upload
