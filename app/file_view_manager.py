from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .file_service import is_image_file
from .ui_helpers import reset_tk_var, clear_text_widget, clear_tree_selection


class FileViewManagerMixin:
    def create_file_view_tab(self) -> None:
        self.viewer_tab.columnconfigure(0, weight=1)
        self.viewer_tab.rowconfigure(0, weight=1)

        self.viewer_outer_pane = ttk.PanedWindow(self.viewer_tab, orient=tk.HORIZONTAL)
        self.viewer_outer_pane.grid(row=0, column=0, sticky="nsew")
        self.viewer_outer_pane.bind("<ButtonRelease-1>", lambda _e: self.save_pane_positions())

        tree_frame = ttk.LabelFrame(self.viewer_outer_pane, text="Dateien", padding=8)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(3, weight=0)
        ttk.Label(tree_frame, text="Verzeichnis:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.file_view_root_var = tk.StringVar(value=self.config_data.get("file_view_root", self.base_folder_var.get()) or self.base_folder_var.get())
        self.file_view_combo = ttk.Combobox(tree_frame, textvariable=self.file_view_root_var, state="readonly")
        self.file_view_combo.grid(row=0, column=0, sticky="ew", padx=(85, 118), pady=(0, 6))
        self.file_view_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_file_view_root_selected())
        ttk.Button(tree_frame, text="Baum...", command=self.choose_file_view_root_tree).grid(row=0, column=0, sticky="e", padx=(8, 0), pady=(0, 6))

        status_frame = ttk.Frame(tree_frame)
        status_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        status_frame.columnconfigure(3, weight=1)
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky="w")
        self.file_view_status_var = tk.StringVar(value="alle")
        self.file_view_status_combo = ttk.Combobox(
            status_frame,
            textvariable=self.file_view_status_var,
            values=["alle", "ohne", "hochgeladen", "erfasst", "geaendert", "rueckfrage", "geprueft", "archiviert"],
            width=18,
            state="readonly",
        )
        self.file_view_status_combo.grid(row=0, column=1, sticky="w", padx=(6, 14))
        self.file_view_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_file_view_tree())
        self.file_view_merge_pdfs_button = ttk.Button(status_frame, text="Ausgewählte PDFs zusammenfassen...", command=self.merge_selected_admin_pdfs)
        self.file_view_merge_pdfs_button.grid(row=0, column=2, sticky="w")
        if not self.is_current_admin():
            self.file_view_merge_pdfs_button.grid_remove()

        filter_frame = ttk.Frame(tree_frame)
        filter_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Suche/Filter:").grid(row=0, column=0, sticky="w")
        self.file_view_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.file_view_filter_var).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(filter_frame, text="Suchen", command=self.refresh_file_view_tree).grid(row=0, column=2, sticky="e")
        ttk.Button(filter_frame, text="Zurücksetzen", command=self.clear_file_view_filter).grid(row=0, column=3, sticky="e", padx=(6, 0))

        self.file_tree = ttk.Treeview(tree_frame, columns=("path",), show="tree", selectmode="extended", height=20)
        self.file_tree.tag_configure("folder_has_files", background="#fff2cc")
        self.file_tree.tag_configure("large_pdf", foreground="#b00020")
        self.file_tree.tag_configure("pdfa_file", background="#e8f7e8")
        self.file_tree.tag_configure("ocr_file", background="#fff9cc")
        self.file_tree.grid(row=3, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", lambda _e: self.on_file_tree_select())
        self.file_tree.bind("<Double-1>", lambda _e: self.open_selected_file_from_tree())
        self.file_tree.bind("<Button-3>", self.show_file_tree_context_menu)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=3, column=1, sticky="ns")
        hsb.grid(row=4, column=0, sticky="ew")

        self.file_view_actions_frame = ttk.LabelFrame(tree_frame, text="Admin-Aktionen", padding=8)
        self.admin_openai_frame = ttk.Frame(tree_frame)
        self.admin_openai_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.admin_openai_frame.columnconfigure(4, weight=1)
        self.admin_openai_button = ttk.Button(self.admin_openai_frame, text="OpenAI prüfen", command=self.admin_openai_selected_document)
        self.admin_openai_button.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.admin_openai_places_button = ttk.Button(self.admin_openai_frame, text="Orte prüfen", command=self.admin_openai_place_scan_selected_document)
        self.admin_openai_places_button.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.admin_place_contexts_button = ttk.Button(self.admin_openai_frame, text="Fundstellen anzeigen", command=self.show_admin_place_contexts_dialog)
        self.admin_place_contexts_button.grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.admin_ocr_pdf_button = ttk.Button(self.admin_openai_frame, text="PDF OCR erstellen", command=self.admin_create_ocr_for_selected_document)
        self.admin_ocr_pdf_button.grid(row=0, column=3, sticky="w", padx=(0, 8))
        self.admin_openai_status_var = tk.StringVar(value="OpenAI: keine Datei ausgewählt")
        ttk.Label(self.admin_openai_frame, textvariable=self.admin_openai_status_var, foreground="#555555").grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

        self.file_view_actions_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.file_view_actions_frame.columnconfigure(1, weight=1)
        self.new_status_label = ttk.Label(self.file_view_actions_frame, text="Dokumentstatus:")
        self.new_status_label.grid(row=0, column=0, sticky="w")
        self.new_status_var = tk.StringVar(value="")
        self.new_status_combo = ttk.Combobox(
            self.file_view_actions_frame,
            textvariable=self.new_status_var,
            values=["hochgeladen", "erfasst", "geaendert", "rueckfrage", "geprueft", "archiviert"],
            width=18,
            state="readonly",
        )
        self.new_status_combo.grid(row=0, column=1, sticky="w", padx=6)
        self.new_status_combo.bind("<<ComboboxSelected>>", lambda _e: self.admin_set_status(silent=True))
        ttk.Label(self.file_view_actions_frame, text="Datei ablegen in:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.file_view_destination_var = tk.StringVar()
        self.file_view_destination_combo = ttk.Combobox(self.file_view_actions_frame, textvariable=self.file_view_destination_var, state="readonly")
        self.file_view_destination_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(self.file_view_actions_frame, text="Baum...", command=self.choose_file_view_destination).grid(row=1, column=2, sticky="e", pady=(6, 0))
        ttk.Label(self.file_view_actions_frame, text="Neuer Dateiname:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.file_view_new_filename_var = tk.StringVar()
        ttk.Entry(self.file_view_actions_frame, textvariable=self.file_view_new_filename_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.file_view_rename_button = ttk.Button(self.file_view_actions_frame, text="Datei umbenennen / verschieben", command=self.file_view_rename_or_move)
        self.file_view_rename_button.grid(row=2, column=2, sticky="e", pady=(6, 0))
        points_frame = ttk.Frame(self.file_view_actions_frame)
        points_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Label(points_frame, text="Punkte Dokument:").pack(side="left")
        self.admin_document_points_var = tk.StringVar(value="keine Datei ausgewählt")
        ttk.Label(points_frame, textvariable=self.admin_document_points_var).pack(side="left", padx=(6, 18))
        self.manual_points_button = ttk.Button(points_frame, text="Sonderpunkte erfassen...", command=lambda: self.open_manual_points_dialog(item=self.selected_admin_upload()))
        self.manual_points_button.pack(side="left", padx=(0, 8))
        self.point_details_button = ttk.Button(points_frame, text="Punktdetails...", command=self.open_document_points_detail_dialog)
        self.point_details_button.pack(side="left")
        if not self.is_current_admin():
            self.file_view_actions_frame.grid_remove()

        right_notebook = ttk.Notebook(self.viewer_outer_pane)
        self.viewer_right_notebook = right_notebook
        self.viewer_outer_pane.add(tree_frame, weight=1)
        self.viewer_outer_pane.add(right_notebook, weight=2)

        meta_outer = ttk.Frame(right_notebook, padding=8)
        meta_outer.columnconfigure(0, weight=1)
        meta_outer.rowconfigure(0, weight=1)
        right_notebook.add(meta_outer, text="Metadaten")

        preview_frame = ttk.Frame(right_notebook, padding=8)
        self.file_view_preview_tab = preview_frame
        preview_frame.columnconfigure(0, weight=0)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        self.show_persons_var = tk.BooleanVar(value=True)
        self.show_persons_check = ttk.Checkbutton(preview_frame, text="Personen anzeigen", variable=self.show_persons_var, command=self.show_file_preview)
        self.show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.show_persons_check.grid_remove()
        self.person_legend_text, legend_frame = self.make_scrolled_text(preview_frame, height=8, wrap="word")
        self.person_legend_frame = legend_frame
        legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.person_legend_text.configure(width=32, state="disabled")
        self.file_preview_label = ttk.Label(preview_frame, text="Keine Datei ausgewählt.", anchor="center")
        self.file_preview_label.grid(row=1, column=1, sticky="nsew")
        self.file_preview_label.bind("<Double-1>", lambda _e: self.edit_persons_for_current_file())
        self.file_preview_zoom = 1.0
        self.file_preview_label.bind("<MouseWheel>", self.on_file_preview_mousewheel)
        self.file_preview_label.bind("<Button-4>", self.on_file_preview_mousewheel)
        self.file_preview_label.bind("<Button-5>", self.on_file_preview_mousewheel)

        meta_canvas = tk.Canvas(meta_outer, highlightthickness=0)
        meta_scroll = ttk.Scrollbar(meta_outer, orient="vertical", command=meta_canvas.yview)
        meta_frame = ttk.Frame(meta_canvas)
        meta_window = meta_canvas.create_window((0, 0), window=meta_frame, anchor="nw")
        meta_frame.bind("<Configure>", lambda _e: meta_canvas.configure(scrollregion=meta_canvas.bbox("all")))
        meta_canvas.bind("<Configure>", lambda e: meta_canvas.itemconfigure(meta_window, width=e.width))
        meta_canvas.configure(yscrollcommand=meta_scroll.set)
        meta_canvas.grid(row=0, column=0, sticky="nsew")
        meta_scroll.grid(row=0, column=1, sticky="ns")
        self.file_view_meta_canvas = meta_canvas
        for scroll_widget in (meta_canvas, meta_frame):
            scroll_widget.bind("<Enter>", lambda _e: meta_canvas.bind_all("<MouseWheel>", self.on_file_view_meta_mousewheel))
            scroll_widget.bind("<Leave>", lambda _e: meta_canvas.unbind_all("<MouseWheel>"))

        self.file_view_write_hint_var = tk.StringVar(value="")
        ttk.Label(meta_frame, textvariable=self.file_view_write_hint_var).grid(row=0, column=0, sticky="w", pady=(0, 6))
        metadata_form_frame = ttk.Frame(meta_frame)
        metadata_form_frame.grid(row=1, column=0, sticky="nsew")
        meta_frame.columnconfigure(0, weight=1)
        meta_frame.rowconfigure(1, weight=1)
        form = self.create_metadata_form_two_columns(metadata_form_frame, "file_view")
        self.file_view_meta_vars = form["vars"]  # type: ignore[assignment]
        self.file_view_meta_widgets = form["widgets"]  # type: ignore[assignment]
        self.file_view_description_text = form["description_text"]  # type: ignore[assignment]
        self.file_view_description_counter_var = form.get("description_counter_var")  # type: ignore[assignment]
        self.file_view_note_text = form["note_text"]  # type: ignore[assignment]
        self.file_view_json_text = form["json_text"]  # type: ignore[assignment]

        self.update_file_view_preview_tab_visibility()
        self.after(200, self.restore_pane_positions)
        self.refresh_file_view_folder_choices()
        self.refresh_file_view_destination_choices()

    def update_file_view_preview_tab_visibility(self) -> None:
        notebook = self.viewer_right_notebook
        preview_tab = self.file_view_preview_tab
        if notebook is None or preview_tab is None:
            return
        path = self.file_view_current_path
        show_preview = bool(path and Path(path).exists() and Path(path).is_file() and is_image_file(Path(path)))
        tabs = [str(tab) for tab in notebook.tabs()]
        preview_id = str(preview_tab)
        if show_preview:
            if preview_id not in tabs:
                try:
                    notebook.add(preview_tab, text="Vorschau / Personen")
                except tk.TclError:
                    notebook.tab(preview_tab, state="normal")
            else:
                try:
                    notebook.tab(preview_tab, state="normal")
                except tk.TclError:
                    pass
        elif not show_preview and preview_id in tabs:
            try:
                if notebook.select() == preview_id:
                    notebook.select(0)
                notebook.hide(preview_tab)
            except Exception:
                pass
        if not show_preview:
            self.file_preview_image = None
            self.file_preview_label.configure(image="", text="")

    def clear_file_view_selection(self) -> None:
        """Leert Dateiansicht, Vorschau und Metadaten, bis bewusst eine Datei ausgewählt wird."""
        self.file_view_current_path = None
        self.file_view_current_metadata = None
        self.file_preview_zoom = 1.0
        clear_tree_selection(self.file_tree)
        self.file_preview_image = None
        self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        self.update_file_view_preview_tab_visibility()
        self.show_persons_check.grid_remove()
        self.person_legend_frame.grid_remove()
        self.person_legend_text.configure(state="normal")
        self.person_legend_text.delete("1.0", "end")
        self.person_legend_text.configure(state="disabled")
        self.file_view_write_hint_var.set("Keine Datei ausgewählt.")
        self.update_file_view_ocr_button()
        for var in self.file_view_meta_vars.values():
            reset_tk_var(var)
        clear_text_widget(self.file_view_description_text, disable_after=True)
        clear_text_widget(self.file_view_note_text, disable_after=True)
        clear_text_widget(self.file_view_json_text, "Keine Datei ausgewählt.", disable_after=True)
        for widget in self.file_view_meta_widgets:
            try:
                widget.configure(state="disabled")
            except Exception:
                pass
        self.update_file_view_admin_actions_for_selection()
