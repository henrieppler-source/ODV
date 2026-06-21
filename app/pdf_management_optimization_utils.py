from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import importlib.util
import os
import subprocess
import time

from tkinter import messagebox

from .app_logging import app_log_exception
from .file_service import append_metadata_history, save_metadata_file


def optimize_pdf_file(manager: Any, source: Path, parent=None) -> None:
    manager.keep_pdf_overview_front(parent)
    if not manager.ensure_local_pdf_available(source, parent=parent):
        return
    profile = manager.pdf_optimization_profile()
    if not messagebox.askyesno(
        "PDF optimieren",
        f"PDF mit Optimierungsprofil '{profile}' optimieren?\n\nDatei:\n{source}\n\n"
        "ODV erstellt zuerst eine temporäre Datei und ersetzt die Arbeitsdatei nur, wenn die optimierte Datei kleiner ist.",
        parent=parent,
    ):
        manager.keep_pdf_overview_front(parent)
        return
    temp = source.with_name(f"{source.stem}.__odv_optimized_tmp.pdf")
    original_size = source.stat().st_size
    display_name = manager._pdf_action_user_label()

    def worker() -> dict:
        if temp.exists():
            temp.unlink()
        tool = "pymupdf"
        if profile in {"standard", "maximal"}:
            gs = manager.find_ghostscript_command()
            if gs:
                manager.run_ghostscript_pdf_optimization(source, temp, gs, profile)
                tool = "ghostscript"
            else:
                manager.run_lossless_pdf_optimization(source, temp, profile)
        else:
            manager.run_lossless_pdf_optimization(source, temp, profile)
        optimized_size = temp.stat().st_size if temp.exists() else 0
        if optimized_size <= 0:
            raise RuntimeError("Optimierte PDF-Datei wurde nicht erstellt.")
        if optimized_size >= original_size:
            try:
                temp.unlink()
            except Exception:
                pass
            manager.record_pdf_optimization_attempt(source, original_size, optimized_size, tool, profile, display_name=display_name)
            return {"changed": False, "original_size": original_size, "optimized_size": optimized_size, "tool": tool}
        replace_error = None
        for _attempt in range(5):
            try:
                os.replace(str(temp), str(source))
                replace_error = None
                break
            except PermissionError as exc:
                replace_error = exc
                time.sleep(0.8)
        if replace_error is not None:
            raise PermissionError(
                "Die optimierte PDF wurde erzeugt, aber die Originaldatei konnte nicht ersetzt werden.\n\n"
                "Wahrscheinlich ist die Datei gerade geöffnet oder gesperrt, z. B. durch Adobe Reader, "
                "Explorer-Vorschau, Windows-Suche oder Nextcloud-Sync.\n\n"
                "Bitte Datei schließen, kurz auf den Nextcloud-Sync warten und die Optimierung erneut starten."
            ) from replace_error
        manager.record_pdf_optimization(source, original_size, optimized_size, tool, profile, display_name=display_name)
        return {"changed": True, "original_size": original_size, "optimized_size": optimized_size, "tool": tool}

    def finish(result, error) -> None:
        if error:
            try:
                if temp.exists():
                    temp.unlink()
            except Exception:
                pass
            app_log_exception("PDF konnte nicht optimiert werden", error, source=str(source))
            messagebox.showerror("PDF optimieren", f"PDF konnte nicht optimiert werden:\n{error}", parent=parent)
            manager.keep_pdf_overview_front(parent)
            return
        manager.refresh_pdf_views_after_action()
        if not result.get("changed"):
            messagebox.showinfo(
                "PDF optimieren",
                "Die PDF-Optimierung hat keine kleinere Datei ergeben.\n"
                f"Arbeitsdatei bleibt unverändert: {manager.format_size_bytes(result.get('original_size'))}\n\n"
                "Der Optimierungsversuch wird in der PDF-Übersicht mit X dokumentiert.",
                parent=parent,
            )
            manager.keep_pdf_overview_front(parent)
            return
        saved = int(result.get("original_size") or 0) - int(result.get("optimized_size") or 0)
        messagebox.showinfo(
            "PDF optimieren",
            f"PDF wurde mit Profil '{profile}' optimiert.\n\n"
            f"Vorher: {manager.format_size_bytes(result.get('original_size'))}\n"
            f"Nachher: {manager.format_size_bytes(result.get('optimized_size'))}\n"
            f"Ersparnis: {manager.format_size_bytes(saved)}\n\n"
            "Die Änderung wird über den Nextcloud-Sync hochgeladen.",
            parent=parent,
        )
        manager.keep_pdf_overview_front(parent)

    manager.run_pdf_processing_dialog(
        "PDF optimieren",
        f"Datei wird verarbeitet...\n\n{source.name}",
        worker,
        finish,
        parent=parent,
    )


def run_lossless_pdf_optimization(manager: Any, source: Path, target: Path, profile: str | None = None) -> None:
    if importlib.util.find_spec("fitz") is None:
        raise RuntimeError("PyMuPDF ist nicht verfügbar. Verlustfreie PDF-Optimierung kann nicht ausgeführt werden.")
    import fitz

    selected_profile = (profile or manager.pdf_optimization_profile()).strip().lower()
    save_options = {"garbage": 4, "deflate": True, "clean": True}
    if selected_profile == "standard":
        save_options.update({"deflate_images": True, "deflate_fonts": True})
    elif selected_profile == "maximal":
        save_options.update({"deflate_images": True, "deflate_fonts": True, "use_objstms": 1, "compression_effort": 9})
    doc = fitz.open(str(source))
    try:
        doc.save(str(target), **save_options)
    finally:
        doc.close()


def run_ghostscript_pdf_optimization(manager: Any, source: Path, target: Path, gs_command: list[str], profile: str) -> None:
    selected_profile = (profile or "standard").strip().lower()
    if selected_profile == "maximal":
        dpi = 120
        mono_dpi = 200
        jpeg_quality = 65
    else:
        dpi = 144
        mono_dpi = 300
        jpeg_quality = 75
    cmd = gs_command + [
        "-dBATCH",
        "-dNOPAUSE",
        "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",
        "-dColorImageDownsampleThreshold=1.0",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dMonoImageDownsampleThreshold=1.0",
        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={mono_dpi}",
        "-dAutoFilterColorImages=false",
        "-dAutoFilterGrayImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dGrayImageFilter=/DCTEncode",
        f"-dJPEGQ={jpeg_quality}",
        f"-sOutputFile={target}",
        str(source),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Ghostscript konnte PDF nicht optimieren.").strip()
        raise RuntimeError(message[:1600])
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("Ghostscript hat keine gültige optimierte PDF-Datei erzeugt.")


def record_pdf_optimization(manager: Any, source: Path, original_size: int, optimized_size: int, tool: str, profile: str, display_name: str | None = None) -> None:
    item, metadata_file = manager.ensure_pdf_metadata_item(source)
    display_name = display_name or manager._pdf_action_user_label()
    item["pdf_optimized_at"] = datetime.now().isoformat(timespec="seconds")
    item["pdf_optimization_attempted_at"] = item["pdf_optimized_at"]
    item["pdf_optimized_by"] = display_name
    item["pdf_original_size_bytes"] = original_size
    item["pdf_optimized_size_bytes"] = optimized_size
    item["pdf_optimization_tool"] = tool
    item["pdf_optimization_profile"] = profile
    item["pdf_optimization_result"] = "optimized"
    append_metadata_history(item, display_name, "PDF optimiert", f"{manager.format_size_bytes(original_size)} -> {manager.format_size_bytes(optimized_size)}; Werkzeug: {tool}; Profil: {profile}")
    save_metadata_file(metadata_file, item)


def record_pdf_optimization_attempt(manager: Any, source: Path, original_size: int, attempted_size: int, tool: str, profile: str, display_name: str | None = None) -> None:
    item, metadata_file = manager.ensure_pdf_metadata_item(source)
    display_name = display_name or manager._pdf_action_user_label()
    now = datetime.now().isoformat(timespec="seconds")
    item["pdf_optimization_attempted_at"] = now
    item["pdf_optimized_by"] = display_name
    item["pdf_original_size_bytes"] = original_size
    item["pdf_optimized_size_bytes"] = attempted_size
    item["pdf_optimization_tool"] = tool
    item["pdf_optimization_profile"] = profile
    item["pdf_optimization_result"] = "no_gain"
    append_metadata_history(item, display_name, "PDF-Optimierung ohne Verkleinerung", f"{manager.format_size_bytes(original_size)} -> {manager.format_size_bytes(attempted_size)}; Werkzeug: {tool}; Profil: {profile}")
    save_metadata_file(metadata_file, item)
    item["_metadata_file"] = str(metadata_file)
