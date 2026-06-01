from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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
        tree_frame.rowconfigure(2, weight=1)
        ttk.Label(tree_frame, text="Verzeichnis:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.file_view_root_var = tk.StringVar(value=self.config_data.get("file_view_root", self.base_folder_var.get()) or self.base_folder_var.get())
        self.file_view_combo = ttk.Combobox(tree_frame, textvariable=self.file_view_root_var, state="readonly")
        self.file_view_combo.grid(row=0, column=0, sticky="ew", padx=(85, 118), pady=(0, 6))
        self.file_view_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_file_view_root_selected())
        ttk.Button(tree_frame, text="Baum...", command=self.choose_file_view_root_tree).grid(row=0, column=0, sticky="e", padx=(8, 0), pady=(0, 6))

        filter_frame = ttk.Frame(tree_frame)
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Suche/Filter:").grid(row=0, column=0, sticky="w")
        self.file_view_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.file_view_filter_var).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(filter_frame, text="Suchen", command=self.refresh_file_view_tree).grid(row=0, column=2, sticky="e")
        ttk.Button(filter_frame, text="Zurücksetzen", command=self.clear_file_view_filter).grid(row=0, column=3, sticky="e", padx=(6, 0))

        self.file_tree = ttk.Treeview(tree_frame, columns=("path",), show="tree")
        self.file_tree.tag_configure("folder_has_files", background="#fff2cc")
        self.file_tree.tag_configure("without_odv_metadata", foreground="#777777")
        self.file_tree.grid(row=2, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", lambda _e: self.on_file_tree_select())
        self.file_tree.bind("<Double-1>", lambda _e: self.open_selected_file_from_tree())
        self.file_tree.bind("<Button-3>", self.show_file_tree_context_menu)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=2, column=1, sticky="ns")
        hsb.grid(row=3, column=0, sticky="ew")

        right_pane = ttk.PanedWindow(self.viewer_outer_pane, orient=tk.VERTICAL)
        self.viewer_right_pane = right_pane
        self.viewer_outer_pane.add(tree_frame, weight=1)
        self.viewer_outer_pane.add(right_pane, weight=2)

        preview_frame = ttk.LabelFrame(right_pane, text="Vorschau / Personen", padding=8)
        preview_frame.columnconfigure(0, weight=0)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        self.show_persons_var = tk.BooleanVar(value=True)
        self.show_persons_check = ttk.Checkbutton(preview_frame, text="Personen anzeigen", variable=self.show_persons_var, command=self.show_file_preview)
        self.show_persons_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.show_persons_check.grid_remove()
        self.file_view_open_ocr_button = ttk.Button(preview_frame, text="OCR anzeigen", command=self.open_file_view_ocr_pdf, state="disabled")
        self.file_view_open_ocr_button.grid(row=0, column=1, sticky="e", pady=(0, 6))
        self.person_legend_text, legend_frame = self.make_scrolled_text(preview_frame, height=8, wrap="word")
        self.person_legend_frame = legend_frame
        legend_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.person_legend_text.configure(width=32, state="disabled")
        self.file_preview_label = ttk.Label(preview_frame, text="Keine Datei ausgewählt.", anchor="center")
        self.file_preview_label.grid(row=1, column=1, sticky="nsew")
        self.file_preview_label.bind("<Double-1>", lambda _e: self.edit_persons_for_current_file())

        meta_outer = ttk.LabelFrame(right_pane, text="Metadaten", padding=8)
        meta_outer.columnconfigure(0, weight=1)
        meta_outer.rowconfigure(0, weight=1)
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

        right_pane.add(preview_frame, weight=1)
        right_pane.add(meta_outer, weight=3)
        self.after(200, self.restore_pane_positions)
        self.refresh_file_view_folder_choices()

    def clear_file_view_selection(self) -> None:
        """Leert Dateiansicht, Vorschau und Metadaten, bis bewusst eine Datei ausgewählt wird."""
        self.file_view_current_path = None
        self.file_view_current_metadata = None
        clear_tree_selection(self.file_tree)
        if hasattr(self, "file_preview_label"):
            self.file_preview_image = None
            self.file_preview_label.configure(image="", text="Keine Datei ausgewählt.")
        if hasattr(self, "show_persons_check"):
            self.show_persons_check.grid_remove()
        if hasattr(self, "person_legend_frame"):
            self.person_legend_frame.grid_remove()
        if hasattr(self, "person_legend_text"):
            self.person_legend_text.configure(state="normal")
            self.person_legend_text.delete("1.0", "end")
            self.person_legend_text.configure(state="disabled")
        if hasattr(self, "file_view_write_hint_var"):
            self.file_view_write_hint_var.set("Keine Datei ausgewählt.")
        self.update_file_view_ocr_button()
        if hasattr(self, "file_view_meta_vars"):
            for var in self.file_view_meta_vars.values():
                reset_tk_var(var)
        for attr in ("file_view_description_text", "file_view_note_text", "file_view_json_text"):
            widget = getattr(self, attr, None)
            if widget is not None:
                clear_text_widget(widget, "Keine Datei ausgewählt." if attr == "file_view_json_text" else None, disable_after=True)
        for widget in getattr(self, "file_view_meta_widgets", []):
            try:
                widget.configure(state="disabled")
            except Exception:
                pass
