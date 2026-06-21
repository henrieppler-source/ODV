from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import os
import shutil
import subprocess

from tkinter import messagebox

from .app_logging import app_log_exception
from .file_service import append_metadata_history, save_metadata_file


def ensure_local_pdf_available(manager: Any, source: Path, parent=None) -> bool:
    if source.exists() and source.is_file() and source.suffix.lower() == ".pdf":
        return True
    messagebox.showwarning(
        "PDF",
        "Diese PDF ist in Nextcloud vorgesehen, aber lokal nicht verfügbar.\n"
        "Bitte die Datei zuerst synchronisieren/herunterladen.",
        parent=parent,
    )
    manager.keep_pdf_overview_front(parent)
    return False


def create_pdfa_file(manager: Any, source: Path, parent=None) -> None:
    manager.keep_pdf_overview_front(parent)
    if not ensure_local_pdf_available(manager, source, parent=parent):
        return
    target = manager.pdfa_path_for_document(source)
    if not target:
        messagebox.showwarning("PDF/A", "Bitte eine PDF-Datei auswählen.", parent=parent)
        manager.keep_pdf_overview_front(parent)
        return
    if target.exists():
        messagebox.showinfo("PDF/A", f"PDF/A-Fassung ist bereits vorhanden:\n{target}", parent=parent)
        manager.keep_pdf_overview_front(parent)
        return
    gs = manager.find_ghostscript_command()
    if not gs:
        messagebox.showwarning(
            "PDF/A",
            "Ghostscript wurde nicht gefunden.\n\n"
            "PDF/A-Erzeugung wird erst aktiviert, wenn Ghostscript installiert bzw. im PATH verfügbar ist.",
            parent=parent,
        )
        manager.keep_pdf_overview_front(parent)
        return
    if not messagebox.askyesno("PDF/A erzeugen", f"PDF/A-Archivfassung erzeugen?\n\nQuelle:\n{source}\n\nZiel:\n{target}", parent=parent):
        manager.keep_pdf_overview_front(parent)
        return
    temp = target.with_name(f"{target.stem}.__odv_pdfa_tmp.pdf")
    display_name = manager.display_name_var.get().strip() or "ODV"

    def worker() -> dict:
        if temp.exists():
            temp.unlink()
        manager.run_ghostscript_pdfa(source, temp, gs)
        shutil.move(str(temp), str(target))
        manager.record_pdfa_creation(source, target, gs[0], display_name=display_name)
        return {"target": target}

    def finish(result, error) -> None:
        if error:
            try:
                if temp.exists():
                    temp.unlink()
            except Exception:
                pass
            app_log_exception("PDF/A konnte nicht erzeugt werden", error, source=str(source), target=str(target))
            messagebox.showerror("PDF/A", f"PDF/A konnte nicht erzeugt werden:\n{error}", parent=parent)
            manager.keep_pdf_overview_front(parent)
            return
        messagebox.showinfo(
            "PDF/A",
            f"PDF/A-Fassung wurde erzeugt:\n{target}\n\nDie Datei wird über den Nextcloud-Sync hochgeladen.",
            parent=parent,
        )
        manager.refresh_pdf_views_after_action()
        manager.keep_pdf_overview_front(parent)

    manager.run_pdf_processing_dialog(
        "PDF/A erzeugen",
        f"Datei wird verarbeitet...\n\n{source.name}",
        worker,
        finish,
        parent=parent,
    )


def run_ghostscript_pdfa(manager: Any, source: Path, target: Path, gs_command: list[str]) -> None:
    cmd = gs_command + [
        "-dPDFA=2",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-dPDFACompatibilityPolicy=1",
        "-sColorConversionStrategy=RGB",
        "-sProcessColorModel=DeviceRGB",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        f"-sOutputFile={target}",
        str(source),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Ghostscript konnte PDF/A nicht erzeugen.").strip()
        raise RuntimeError(message[:1600])
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("Ghostscript hat keine gültige PDF/A-Datei erzeugt.")


def record_pdfa_creation(manager: Any, source: Path, target: Path, tool: str, display_name: str | None = None) -> None:
    item, metadata_file = manager.ensure_pdf_metadata_item(source)
    display_name = display_name or manager._pdf_action_user_label()
    item["pdfa_path"] = str(target)
    item["pdfa_filename"] = target.name
    item["pdfa_created_at"] = datetime.now().isoformat(timespec="seconds")
    item["pdfa_created_by"] = display_name
    item["pdfa_tool"] = tool
    append_metadata_history(item, display_name, "PDF/A erzeugt", f"{source.name} -> {target.name}; Werkzeug: {tool}")
    save_metadata_file(metadata_file, item)
    item["_metadata_file"] = str(metadata_file)
