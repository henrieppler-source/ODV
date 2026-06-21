from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.util
import os
import shutil
import subprocess
import sys
import threading

from tkinter import messagebox

from .app_logging import app_log_exception
from .file_service import unique_path_with_counter


def create_searchable_pdf_for_upload(manager: Any) -> None:
    path = manager.selected_file
    if path is None or path.suffix.lower() != ".pdf":
        messagebox.showwarning("PDF OCR", "Bitte zuerst eine PDF-Datei auswählen.")
        return
    if manager.extract_upload_text_sample(path, max_chars=500):
        if not messagebox.askyesno("PDF OCR", "Dieses PDF enthält bereits lesbaren Text.\n\nTrotzdem eine OCR-PDF-Kopie erstellen?"):
            return

    ocr_backend = manager.find_pdf_ocr_backend()
    if not ocr_backend:
        messagebox.showerror(
            "PDF OCR",
            "Es wurde kein PDF-OCR-Werkzeug gefunden.\n\n"
            "Installiert sein muss entweder OCRmyPDF oder Tesseract mit PyMuPDF. "
            "Danach kann ODV daraus eine durchsuchbare PDF-Kopie erzeugen.",
        )
        return

    target_path = unique_path_with_counter(path.with_name(f"{path.stem}_ocr.pdf"))
    manager.upload_openai_text_var.set("PDF OCR läuft …")
    manager.upload_openai_usage_var.set("Verbrauch: k.A.")
    manager.start_upload_ocr_progress("PDF OCR läuft …")
    thread = threading.Thread(target=manager._run_pdf_ocr, args=(path, target_path, ocr_backend), daemon=True)
    thread.start()


def start_upload_ocr_progress(manager: Any, message: str) -> None:
    manager.upload_ocr_progress_var.set(message)
    manager.upload_ocr_progress_frame.grid()
    manager.upload_ocr_progress.start(12)
    manager.upload_ocr_pdf_button.configure(state="disabled")
    manager.open_file_openai_button.configure(state="disabled")


def stop_upload_ocr_progress(manager: Any) -> None:
    try:
        manager.upload_ocr_progress.stop()
    except Exception:
        pass
    manager.upload_ocr_progress_var.set("")
    manager.upload_ocr_progress_frame.grid_remove()
    manager.update_openai_precheck_indicator()


def find_pdf_ocr_backend(manager: Any) -> tuple[str, Any] | None:
    ocrmypdf_command = manager.find_ocrmypdf_command()
    if ocrmypdf_command:
        return ("ocrmypdf", ocrmypdf_command)
    pymupdf_config = manager.find_pymupdf_ocr_config()
    if pymupdf_config:
        return ("pymupdf", pymupdf_config)
    return None


def find_ocrmypdf_command() -> list[str] | None:
    executable = shutil.which("ocrmypdf")
    if executable:
        return [executable]
    if importlib.util.find_spec("ocrmypdf") is not None:
        return [sys.executable, "-m", "ocrmypdf"]
    return None


def find_tesseract_executable() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files/PDF24/tesseract/tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def local_tessdata_dir() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "tessdata",
        Path(__file__).resolve().parent.parent / "app" / "tessdata",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def find_pymupdf_ocr_config(manager: Any) -> dict[str, str] | None:
    if importlib.util.find_spec("fitz") is None:
        return None
    tesseract = manager.find_tesseract_executable()
    if not tesseract:
        return None
    tessdata = manager.local_tessdata_dir()
    language = "eng"
    tessdata_text = ""
    if tessdata and (tessdata / "deu.traineddata").exists():
        language = "deu"
        tessdata_text = str(tessdata)
    return {"tesseract": tesseract, "language": language, "tessdata": tessdata_text}


def _run_pdf_ocr(manager: Any, source: Path, target: Path, ocr_backend: tuple[str, Any]) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        backend_name, backend_config = ocr_backend
        if backend_name == "pymupdf":
            manager._run_pdf_ocr_with_pymupdf(source, target, backend_config)
        else:
            manager._run_pdf_ocr_with_ocrmypdf(source, target, backend_config)
        manager.after(0, manager.stop_upload_ocr_progress)
        manager.after(0, lambda: manager.link_upload_ocr_pdf(target))
        manager.after(0, lambda: manager.upload_openai_text_var.set("PDF OCR fertig - OCR-PDF verknüpft"))
        manager.after(0, lambda: messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt und verknüpft:\n{target}\n\nDas Original bleibt für den Upload ausgewählt. OpenAI nutzt die OCR-Fassung."))
    except Exception as exc:
        app_log_exception("PDF OCR konnte nicht ausgeführt werden", exc, source=str(source), target=str(target))
        error_message = str(exc)
        manager.after(0, manager.stop_upload_ocr_progress)
        manager.after(0, lambda: manager.upload_openai_text_var.set("PDF OCR fehlgeschlagen"))
        manager.after(0, lambda: messagebox.showerror("PDF OCR", f"OCR konnte nicht ausgeführt werden:\n{error_message}"))


def _run_pdf_ocr_with_ocrmypdf(source: Path, target: Path, ocrmypdf_command: list[str]) -> None:
    cmd = ocrmypdf_command + [
        "--skip-text",
        "--language",
        "deu+eng",
        str(source),
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "OCR konnte nicht abgeschlossen werden.").strip()
        raise RuntimeError(message[:1200])


def _run_pdf_ocr_with_pymupdf(manager: Any, source: Path, target: Path, config: dict[str, str]) -> None:
    import fitz

    tesseract = config.get("tesseract", "")
    if tesseract:
        tesseract_dir = str(Path(tesseract).parent)
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if tesseract_dir not in path_parts:
            os.environ["PATH"] = tesseract_dir + os.pathsep + os.environ.get("PATH", "")

    tessdata = config.get("tessdata", "")
    if tessdata:
        os.environ["TESSDATA_PREFIX"] = tessdata
    language = config.get("language") or "eng"

    src = fitz.open(str(source))
    out = fitz.open()
    try:
        for page in src:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pdf_bytes = pix.pdfocr_tobytes(compress=True, language=language, tessdata=tessdata or None)
            page_doc = fitz.open("pdf", pdf_bytes)
            try:
                out.insert_pdf(page_doc)
            finally:
                page_doc.close()
        out.save(str(target), garbage=4, deflate=True)
    finally:
        out.close()
        src.close()
