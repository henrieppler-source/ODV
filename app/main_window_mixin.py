from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from .app_logging import app_log_exception
from .app_constants import APP_NAME, APP_SHORT_NAME, APP_VERSION
from .single_instance import resource_path


class MainWindowMixin:
    def show_startup_splash(self) -> None:
        """Zeigt beim Programmstart kurz ein Startfenster mit Logo und Anwendungsname."""
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg="white")
        splash.attributes("-topmost", True)

        frame = tk.Frame(splash, bg="white", bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        logo_path = resource_path("app/assets/odv_logo.png")
        logo_photo = None
        if logo_path.exists():
            try:
                img = Image.open(logo_path).convert("RGBA")
                img.thumbnail((170, 170), Image.LANCZOS)
                logo_photo = ImageTk.PhotoImage(img)
                logo_label = tk.Label(frame, image=logo_photo, bg="white")
                logo_label.image = logo_photo
                logo_label.pack(pady=(22, 8))
            except Exception as exc:
                app_log_exception("Splash-Logo konnte nicht geladen werden", exc)

        tk.Label(
            frame,
            text=APP_NAME,
            bg="white",
            fg="#1f1f1f",
            font=("Segoe UI", 17, "bold"),
        ).pack(padx=36, pady=(6, 0))
        tk.Label(
            frame,
            text=f"{APP_SHORT_NAME} · {APP_VERSION}",
            bg="white",
            fg="#555555",
            font=("Segoe UI", 11),
        ).pack(padx=36, pady=(4, 20))
        tk.Label(
            frame,
            text="Dateien · Metadaten · Ortschronik",
            bg="white",
            fg="#777777",
            font=("Segoe UI", 9),
        ).pack(padx=36, pady=(0, 24))

        splash.update_idletasks()
        width = 580
        height = 390
        x = max(0, (splash.winfo_screenwidth() - width) // 2)
        y = max(0, (splash.winfo_screenheight() - height) // 2)
        splash.geometry(f"{width}x{height}+{x}+{y}")
        splash.update()
        self.after(5200, splash.destroy)
        self.wait_window(splash)

    def create_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.create_menu()
        self.create_styles()

        notebook = ttk.Notebook(self)
        self.notebook = notebook
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.create_status_bar()

        self.history_tab = ttk.Frame(notebook, padding=10, style="Dashboard.TFrame")
        self.upload_tab_container = ttk.Frame(notebook, style="Upload.TFrame")
        self.upload_tab = self.make_scrollable_tab(self.upload_tab_container)
        self.viewer_tab = ttk.Frame(notebook, padding=10, style="Viewer.TFrame")
        self.admin_tab = ttk.Frame(notebook, padding=10, style="Admin.TFrame")
        self.admin_tab_visible = True

        notebook.add(self.history_tab, text="Dashboard")
        notebook.add(self.upload_tab_container, text="Dateien hochladen")
        notebook.add(self.viewer_tab, text="Dateien anzeigen/bearbeiten")
        notebook.bind("<<NotebookTabChanged>>", self.on_notebook_tab_changed)

        self.create_history_tab()
        self.create_upload_tab()
        self.create_admin_tab()
        self.create_file_view_tab()
        self.ensure_standard_metadata_folder()
        self.apply_selected_user()
        self.update_tab_labels()
        self.update_connection_status()
        self.bind_global_mousewheel()

    def create_status_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 2))
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.api_status_var = tk.StringVar(value="API: wird geprüft …")
        self.nextcloud_status_var = tk.StringVar(value="Nextcloud: nicht geprüft")
        ttk.Label(bar, textvariable=self.api_status_var).grid(row=0, column=0, sticky="w", padx=(0, 20))
        ttk.Label(bar, textvariable=self.nextcloud_status_var).grid(row=0, column=1, sticky="w")

    def update_connection_status(self) -> None:
        if not hasattr(self, "api_status_var"):
            return
        try:
            status = self.api.status()
            api_version = str(status.get("api_version") or status.get("version") or "?")
            version_note = f"API: verbunden ({api_version})"
            if api_version not in ("?", APP_VERSION):
                version_note += f" – Achtung: App {APP_VERSION}"
            maintenance = status.get("maintenance") or {}
            if maintenance.get("active"):
                version_note += " – Wartungsmodus aktiv"
            elif maintenance.get("scheduled"):
                version_note += " – Wartung geplant"
            self.api_status_var.set(version_note)
            self.report_current_device_version()
        except Exception as exc:
            self.api_status_var.set("API: nicht erreichbar")
            app_log_exception("API-Statusprüfung fehlgeschlagen", exc)
        try:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            if base and base.exists() and base.is_dir():
                self.nextcloud_status_var.set(f"Nextcloud: gefunden ({base})")
            else:
                self.nextcloud_status_var.set("Nextcloud: Stammverzeichnis nicht gesetzt/gefunden")
        except Exception as exc:
            self.nextcloud_status_var.set("Nextcloud: Fehler bei Prüfung")
            app_log_exception("Nextcloud-Stammverzeichnis konnte nicht geprüft werden", exc)

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Stammdaten...", command=self.open_masterdata_dialog)
        file_menu.add_command(label="Nextcloud-Zielordner neu prüfen", command=self.load_writable_folders)
        file_menu.add_separator()
        file_menu.add_command(label="Benutzer wechseln...", command=self.logout_and_login)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)

        # Admin: echte Verwaltung / Betrieb
        if self.current_role() == "Superadmin":
            admin_menu = tk.Menu(menubar, tearoff=False)
            admin_menu.add_command(label="Admin-Einstellungen...", command=self.open_admin_settings_dialog)
            admin_menu.add_command(label="Normalisierung...", command=self.open_filename_normalization_dialog)
            admin_menu.add_command(label="Betriebsmodus...", command=self.open_operating_mode_dialog)

            user_admin_menu = tk.Menu(admin_menu, tearoff=False)
            user_admin_menu.add_command(label="Benutzer verwalten...", command=self.open_user_management_dialog)
            admin_menu.add_cascade(label="Benutzerverwaltung", menu=user_admin_menu)

            masterdata_menu = tk.Menu(admin_menu, tearoff=False)
            masterdata_menu.add_command(label="Ortsordner-Stammdaten...", command=self.open_place_folder_dialog)
            masterdata_menu.add_command(label="Archiv/Sammlung-Stammdaten...", command=self.open_archive_collection_dialog)
            admin_menu.add_cascade(label="Stammdaten", menu=masterdata_menu)

            file_admin_menu = tk.Menu(admin_menu, tearoff=False)
            file_admin_menu.add_command(label="Vorhandene Dateien einlesen...", command=self.open_import_existing_files_dialog)
            file_admin_menu.add_command(label="Lokale Sicherungsdateien prüfen/bereinigen...", command=self.open_local_backup_cleanup_dialog)
            admin_menu.add_cascade(label="Dateien", menu=file_admin_menu)

            mail_admin_menu = tk.Menu(admin_menu, tearoff=False)
            mail_admin_menu.add_command(label="Standard-Mail-Texte...", command=self.open_standard_mail_texts_dialog)
            admin_menu.add_cascade(label="Mail", menu=mail_admin_menu)

            database_menu = tk.Menu(admin_menu, tearoff=False)
            database_menu.add_command(label="Wartungsmodus / Datenbanksperre...", command=self.open_maintenance_dialog)
            database_menu.add_command(label="Datenbankmigrationen prüfen/ausführen...", command=self.open_database_migrations_dialog)
            database_menu.add_command(label="Datenbank zurücksetzen...", command=self.open_database_reset_dialog)
            database_menu.add_separator()
            database_menu.add_command(label="Datenbank sichern...", command=self.open_database_backup_dialog)
            database_menu.add_command(label="Backup zurücksichern...", command=self.open_database_restore_dialog)
            admin_menu.add_cascade(label="Datenbank", menu=database_menu)

            server_menu = tk.Menu(admin_menu, tearoff=False)
            server_menu.add_command(label="routes.php sichern/hochladen...", command=self.open_routes_deploy_dialog)
            admin_menu.add_cascade(label="Server", menu=server_menu)

            update_menu = tk.Menu(admin_menu, tearoff=False)
            update_menu.add_command(label="ODV-Updatefreigabe verwalten...", command=self.open_app_update_admin_dialog)
            admin_menu.add_cascade(label="Updates", menu=update_menu)
            menubar.add_cascade(label="Admin", menu=admin_menu)

        # Punkte: alles rund um automatische und manuelle Punkte
        points_menu = tk.Menu(menubar, tearoff=False)
        points_menu.add_command(label="Mein Punktestand...", command=self.open_my_points_dialog)
        if self.is_current_admin():
            document_points_label = "Sonderpunkte zum ausgewählten Dokument..."

            def is_file_view_active() -> bool:
                try:
                    return hasattr(self, "notebook") and self.notebook.select() == str(self.viewer_tab)
                except Exception:
                    return False

            def update_points_menu() -> None:
                try:
                    end = points_menu.index("end")
                    if end is not None:
                        for idx in range(end, -1, -1):
                            try:
                                if points_menu.entrycget(idx, "label") == document_points_label:
                                    points_menu.delete(idx)
                            except tk.TclError:
                                pass
                    if is_file_view_active():
                        points_menu.insert_command(4, label=document_points_label, command=self.open_manual_points_dialog)
                except tk.TclError:
                    pass

            points_menu.configure(postcommand=update_points_menu)
            points_menu.add_separator()
            points_menu.add_command(label="Punkteübersicht...", command=self.open_points_summary_dialog)
            points_menu.add_command(label="Manuelle Sonderpunkte vergeben...", command=self.open_manual_special_points_dialog)
            points_menu.add_command(label="Übersicht manuelle Sonderpunkte...", command=self.open_manual_special_points_overview_dialog)
            if self.current_role() == "Superadmin":
                points_menu.add_separator()
                points_menu.add_command(label="Punkteregeln verwalten...", command=self.open_point_rules_dialog)
                points_menu.add_command(label="Punkte für vorhandene Dokumente neu berechnen...", command=self.recalculate_points_for_visible_admin_uploads)
                points_menu.add_command(label="Punkte-Einstellungen...", command=self.open_points_settings_dialog)
        menubar.add_cascade(label="Punkte", menu=points_menu)

        mail_menu = tk.Menu(menubar, tearoff=False)
        mail_menu.add_command(label="Rundmail erstellen...", command=self.open_information_mail_dialog)
        mail_menu.add_command(label="Verteiler verwalten...", command=self.open_mail_group_management_dialog)
        mail_menu.add_command(label="Versandhistorie...", command=self.open_mail_history_dialog)
        if self.is_current_admin():
            mail_menu.add_separator()
            mail_menu.add_command(label="Standard-Mail-Texte...", command=self.open_standard_mail_texts_dialog)
        menubar.add_cascade(label="Mail", menu=mail_menu)

        if self.is_current_admin():
            overview_menu = tk.Menu(menubar, tearoff=False)
            overview_menu.add_command(label="Dokumentzugriffe...", command=self.open_document_access_log_dialog)
            overview_menu.add_command(label="Sitzungen und Geräte...", command=self.open_sessions_devices_dialog)
            overview_menu.add_command(label="PDF-Dateien...", command=self.open_pdf_overview_dialog)
            overview_menu.add_command(label="Backup-Status...", command=self.open_backup_status_dialog)
            menubar.add_cascade(label="Übersichten", menu=overview_menu)

        # Der frühere Menüpunkt "Ansicht" wurde entfernt.
        # Aktualisierungen erfolgen automatisch beim Reiterwechsel bzw. durch die jeweiligen Bedienaktionen;
        # Spaltenbreiten werden automatisch gespeichert.

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Handbuch", command=lambda: self.open_markdown_handbook("Handbuch.md", "ODV-Handbuch"))
        if self.is_current_admin():
            help_menu.add_command(label="Admin-Handbuch", command=lambda: self.open_markdown_handbook("Admin-Handbuch.md", "ODV-Admin-Handbuch"))
        if self.current_role() == "Superadmin":
            help_menu.add_command(label="Versionshistorie", command=lambda: self.open_markdown_handbook("README.md", "ODV-Versionshistorie"))
        help_menu.add_separator()
        help_menu.add_command(label="Info", command=lambda: messagebox.showinfo(APP_NAME, f"{APP_NAME} ({APP_SHORT_NAME}) {APP_VERSION}\nNextcloud, API/MySQL\n(c) Henri Eppler, 2026"))
        help_menu.add_command(label="Systemstatus...", command=self.open_system_status_dialog)
        if self.is_current_admin():
            help_menu.add_command(label="Logdateien öffnen...", command=self.open_log_folder)
        help_menu.add_command(label="Nach ODV-Update suchen...", command=lambda: self.check_app_update(interactive=True))
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.config(menu=menubar)
