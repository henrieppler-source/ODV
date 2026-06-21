from __future__ import annotations

from pathlib import Path
from typing import Any
import threading

import tkinter as tk
from tkinter import messagebox, ttk


def keep_pdf_overview_front(manager: Any, parent=None) -> None:
    """Bring the PDF overview back after child dialogs/actions."""
    if not parent:
        return
    try:
        parent.lift()
        parent.focus_force()
        parent.attributes("-topmost", True)
        parent.after(250, lambda: parent.attributes("-topmost", False))
    except Exception:
        pass


def run_pdf_processing_dialog(manager: Any, title: str, text: str, worker, finish, parent=None) -> None:
    dialog = tk.Toplevel(parent or manager)
    dialog.title(title)
    dialog.transient(parent or manager)
    dialog.resizable(False, False)
    dialog.columnconfigure(0, weight=1)
    ttk.Label(dialog, text=text, padding=(18, 14, 18, 8)).grid(row=0, column=0, sticky="ew")
    progress = ttk.Progressbar(dialog, mode="indeterminate", length=360)
    progress.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
    ttk.Label(dialog, text="Bitte warten. Große PDFs können mehrere Minuten dauern.", foreground="#555555").grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)
    try:
        dialog.grab_set()
    except Exception:
        pass
    progress.start(12)
    keep_pdf_overview_front(manager, dialog)

    def run() -> None:
        try:
            result = worker()
            manager.after(0, lambda result=result: close_and_finish(result=result, error=None))
        except Exception as exc:
            manager.after(0, lambda error=exc: close_and_finish(result=None, error=error))

    def close_and_finish(result=None, error=None) -> None:
        try:
            progress.stop()
            dialog.grab_release()
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass
        finish(result, error)

    threading.Thread(target=run, daemon=True).start()


def open_linked_pdfa_for_current_file(manager: Any, path: Path | None = None) -> None:
    source = path or manager.file_view_current_path
    pdfa = manager.pdfa_path_for_document(source)
    if not pdfa or not pdfa.exists():
        messagebox.showwarning("PDF/A", "Zu dieser Datei wurde keine PDF/A-Fassung gefunden.")
        return
    manager.open_file_with_default_app(pdfa)


def pdf_action_stub(manager: Any, action: str, path: Path | None = None, parent=None) -> None:
    keep_pdf_overview_front(manager, parent)
    source = path or manager.file_view_current_path
    if not source or source.suffix.lower() != ".pdf":
        messagebox.showwarning("PDF", "Bitte eine PDF-Datei auswählen.", parent=parent)
        keep_pdf_overview_front(manager, parent)
        return
    if action == "PDF optimieren":
        info = manager.pdf_optimization_info_for_path(source)
        if info:
            timestamp = info.get("optimized_at") or info.get("attempted_at") or "unbekannt"
            result_hint = "optimiert" if info.get("optimized_at") else "ohne kleinere Datei geprüft"
            detail = f"Dieses PDF wurde bereits am {timestamp} durch {info['optimized_by']} {result_hint}."
            if manager.is_current_admin():
                if not messagebox.askyesno("PDF optimieren", f"{detail}\nErneute Optimierung kann Qualität verschlechtern.\n\nTrotzdem erneut optimieren?", parent=parent):
                    keep_pdf_overview_front(manager, parent)
                    return
            else:
                messagebox.showwarning("PDF optimieren", f"{detail}\nKeine weitere Optimierung möglich.", parent=parent)
                keep_pdf_overview_front(manager, parent)
                return
        manager.optimize_pdf_file(source, parent=parent)
        return
    if action == "PDF/A erzeugen":
        manager.create_pdfa_file(source, parent=parent)
        return
    messagebox.showinfo(
        "PDF",
        f"{action} ist vorbereitet, aber die eigentliche Verarbeitung wird im nächsten Schritt angebunden.\n\nDatei:\n{source}",
        parent=parent,
    )
    keep_pdf_overview_front(manager, parent)


def open_pdf_overview_dialog(manager: Any) -> None:
    if not manager.is_current_admin():
        return
    base = Path(str(manager.base_folder_var.get() or ""))
    root_options: list[tuple[str, Path]] = []
    if base.exists() and base.is_dir():
        root_options.append((str(base), base))
        try:
            for child in sorted([p for p in base.iterdir() if p.is_dir() and not manager.is_hidden_system_path(p)], key=lambda p: p.name.lower()):
                root_options.append((child.name, child))
        except Exception:
            pass
    dialog = tk.Toplevel(manager)
    dialog.title("Übersicht PDF-Dateien")
    try:
        dialog.transient(manager)
    except Exception:
        pass
    try:
        manager.track_window_geometry(dialog, "Übersicht PDF-Dateien")
    except Exception:
        pass
    dialog.geometry("1100x560")
    dialog.columnconfigure(0, weight=1)
    filter_frame = ttk.Frame(dialog)
    filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 4))
    filter_frame.columnconfigure(1, weight=1)
    ttk.Label(filter_frame, text="Verzeichnis:").grid(row=0, column=0, sticky="w")
    folder_var = tk.StringVar(value=root_options[0][0] if root_options else "")
    folder_combo = ttk.Combobox(filter_frame, textvariable=folder_var, values=[label for label, _path in root_options], state="readonly")
    folder_combo.grid(row=0, column=1, sticky="ew", padx=(6, 12))
    ttk.Label(filter_frame, text="Dateigröße größer:").grid(row=0, column=2, sticky="w")
    min_size_var = tk.StringVar(value="")
    ttk.Entry(filter_frame, textvariable=min_size_var, width=10).grid(row=0, column=3, sticky="w", padx=(6, 4))
    ttk.Label(filter_frame, text="MB").grid(row=0, column=4, sticky="w")
    status_var = tk.StringVar(value="")
    ttk.Label(dialog, textvariable=status_var, font=("", 10, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 2))
    hint_var = tk.StringVar(value="Hinweis: Diese Übersicht zeigt aktuell lokal verfügbare Nextcloud-PDFs. Die zentrale Nextcloud-Dateiliste wird im nächsten Schritt angebunden.")
    ttk.Label(dialog, textvariable=hint_var, foreground="#555555").grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))
    dialog.rowconfigure(3, weight=1)
    columns = ("name", "nextcloud_path", "local_available", "work_size", "original_size", "optimized_by_odv", "pdfa_size", "ocr_size")
    tree = ttk.Treeview(dialog, columns=columns, show="headings", selectmode="browse")
    headings = {
        "name": "Name des PDF (.pdf)",
        "nextcloud_path": "Nextcloud-Pfad",
        "local_available": "Lokal verfügbar",
        "work_size": "Größe Arbeitsdatei",
        "original_size": "Originalgröße",
        "optimized_by_odv": "Optimiert durch ODV",
        "pdfa_size": "Größe PDF/A",
        "ocr_size": "Größe OCR",
    }
    anchors = {
        "name": "w",
        "nextcloud_path": "w",
        "local_available": "e",
        "work_size": "e",
        "original_size": "e",
        "optimized_by_odv": "e",
        "pdfa_size": "e",
        "ocr_size": "e",
    }
    for col, text in headings.items():
        tree.heading(col, text=text, anchor=anchors[col])
        width = 230 if col == "name" else 135
        if col == "nextcloud_path":
            width = 430
        if col == "local_available":
            width = 120
        if col == "optimized_by_odv":
            width = 150
        tree.column(col, width=width, anchor=anchors[col])
    scroll = ttk.Scrollbar(dialog, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.grid(row=3, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
    scroll.grid(row=3, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
    row_by_iid: dict[str, dict[str, str]] = {}
    sort_state = {"column": "work_size", "descending": True}
    load_state = {"id": 0}

    def selected_root() -> Path | None:
        label = folder_var.get().strip()
        return next((path for current_label, path in root_options if current_label == label), None)

    def min_size_mb() -> float:
        text = min_size_var.get().strip().replace(",", ".")
        if not text:
            return 0.0
        try:
            return max(0.0, float(text))
        except ValueError:
            return 0.0

    def sort_key(row: dict[str, str], column: str):
        if column in {"work_size", "original_size", "pdfa_size", "ocr_size"}:
            key_map = {
                "work_size": "work_size_mb",
                "original_size": "original_size_mb",
                "pdfa_size": "pdfa_size_mb",
                "ocr_size": "ocr_size_mb",
            }
            try:
                return float(row.get(key_map[column]) or 0)
            except Exception:
                return 0.0
        return str(row.get(column) or "").casefold()

    def update_headings() -> None:
        for col, text in headings.items():
            marker = " ▼" if sort_state["column"] == col and sort_state["descending"] else " ▲" if sort_state["column"] == col else ""
            tree.heading(col, text=f"{text}{marker}", anchor=anchors[col], command=lambda c=col: set_sort(c))

    def set_sort(column: str) -> None:
        if sort_state["column"] == column:
            sort_state["descending"] = not sort_state["descending"]
        else:
            sort_state["column"] = column
            sort_state["descending"] = column in {"work_size", "original_size", "pdfa_size", "ocr_size"}
        populate()

    def populate() -> None:
        for iid in tree.get_children():
            tree.delete(iid)
        load_state["id"] += 1
        request_id = load_state["id"]
        current_root = selected_root()
        current_sort = sort_state["column"]
        current_descending = bool(sort_state["descending"])
        try:
            threshold = min_size_mb()
        except Exception:
            threshold = 0.0
        status_var.set("PDF-Übersicht wird geladen …")
        row_by_iid.clear()

        def worker() -> None:
            try:
                rows = manager.pdf_report_rows(current_root)
                if threshold:
                    rows = [row for row in rows if float(row.get("work_size_mb") or 0) > threshold]
                rows.sort(key=lambda row: sort_key(row, current_sort), reverse=bool(current_descending))
                try:
                    log_path = manager.write_pdf_size_log(rows)
                except Exception as exc:
                    from .app_logging import app_log_exception
                    app_log_exception("PDF-Größenlog konnte nicht geschrieben werden", exc)
                    log_path = None
            except Exception as exc:
                from .app_logging import app_log_exception
                app_log_exception("PDF-Übersicht konnte nicht geladen werden", exc)
                rows = []
                log_path = None

                def apply_error() -> None:
                    if request_id != load_state["id"]:
                        return
                    status_var.set(f"PDF-Übersicht konnte nicht geladen werden ({exc})")
                manager.after(0, apply_error)
                return

            def apply() -> None:
                if request_id != load_state["id"]:
                    return
                for iid in tree.get_children():
                    tree.delete(iid)
                status_var.set(f"{len(rows)} PDF-Arbeitsdatei(en) gefunden" + (f" | Log: {log_path}" if log_path else ""))
                update_headings()
                for row in rows:
                    iid = tree.insert(
                        "",
                        "end",
                        values=(
                            row["name"],
                            row["nextcloud_path"],
                            row["local_available"],
                            row["work_size"],
                            row["original_size"],
                            row["optimized_by_odv"],
                            row["pdfa_size"],
                            row["ocr_size"],
                        ),
                    )
                    row_by_iid[str(iid)] = row

            manager.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def show_context_menu(event) -> None:
        iid = tree.identify_row(event.y)
        if not iid:
            return
        tree.selection_set(iid)
        row = row_by_iid.get(str(iid)) or {}
        path_text = str(row.get("path") or "")
        path = Path(path_text) if path_text else None
        if not path or not path.exists() or path.suffix.lower() != ".pdf":
            return
        item = manager.item_for_local_path(path) or {}
        linked = manager.linked_pdf_paths_for_item(item, path)
        menu = tk.Menu(dialog, tearoff=False)
        menu.add_command(label="Datei öffnen", command=lambda: manager.open_file_with_default_app(path))
        menu.add_command(label="Download / Kopie speichern unter...", command=lambda: manager.download_file_to_local_folder(path, item))
        if linked.get("ocr"):
            menu.add_command(label="OCR anzeigen", command=lambda p=linked["ocr"]: manager.open_file_with_default_app(p))
        elif manager.find_pdf_ocr_backend():
            menu.add_command(
                label="PDF OCR erstellen...",
                command=lambda: manager.create_ocr_for_document_path(path, item, on_success=populate),
            )
        if linked.get("pdfa"):
            menu.add_command(label="Original / PDF-A anzeigen", command=lambda p=linked["pdfa"]: manager.open_file_with_default_app(p))
        menu.add_separator()
        menu.add_command(label="PDF optimieren...", command=lambda: pdf_action_stub(manager, "PDF optimieren", path, parent=dialog))
        if linked.get("pdfa"):
            menu.add_command(label="PDF/A bereits vorhanden", state="disabled")
        else:
            menu.add_command(label="PDF/A erzeugen...", command=lambda: pdf_action_stub(manager, "PDF/A erzeugen", path, parent=dialog))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    folder_combo.bind("<<ComboboxSelected>>", lambda _e: populate())
    min_size_var.trace_add("write", lambda *_args: populate())
    tree.bind("<Button-3>", show_context_menu)
    populate()
    buttons = ttk.Frame(dialog)
    buttons.grid(row=4, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 12))
    ttk.Button(buttons, text="Aktualisieren", command=populate).pack(side="left", padx=6)
    ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=6)
