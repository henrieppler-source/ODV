from __future__ import annotations

from datetime import datetime
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .app_logging import app_log, app_log_exception
from .config import APP_DIR
from .file_service import append_metadata_history, load_metadata_files, save_metadata_file
from .pdf_management_utils import (
    format_file_size as _pmm_format_file_size,
    format_size_bytes as _pmm_format_size_bytes,
    is_linked_pdfa_file_path as _pmm_is_linked_pdfa_file_path,
    ocr_path_for_document as _pmm_ocr_path_for_document,
    pdfa_path_for_document as _pmm_pdfa_path_for_document,
    pdf_display_prefix as _pmm_pdf_display_prefix,
    pdf_size_mb as _pmm_pdf_size_mb,
    pdf_tree_tags as _pmm_pdf_tree_tags,
    visible_pdf_work_file as _pmm_visible_pdf_work_file,
)
from .pdf_management_tool_utils import (
    build_pdf_tool_search_roots as _pmm_build_pdf_tool_search_roots,
    find_bundled_ghostscript_installer as _pmm_find_bundled_ghostscript_installer,
    find_ghostscript_command as _pmm_find_ghostscript_command,
    ghostscript_executable_candidates as _pmm_ghostscript_executable_candidates,
    ghostscript_installer_candidates as _pmm_ghostscript_installer_candidates,
    install_bundled_ghostscript as _pmm_install_bundled_ghostscript,
    run_ghostscript_installer_elevated as _pmm_run_ghostscript_installer_elevated,
)
from .pdf_management_report_utils import (
    build_pdf_report_rows as _pmm_build_pdf_report_rows,
    write_pdf_size_log as _pmm_write_pdf_size_log,
)


class PdfManagementManagerMixin:
    """PDF-Begleitdateien, Größenhinweise und PDF-Übersichten."""

    def _pdf_action_user_label(self) -> str:
        return self.display_name_var.get().strip() or self.username_var.get().strip() or "ODV"

    def pdf_warning_mb(self) -> int:
        return self._config_int("pdf_warning_mb", 100)

    def pdf_optimize_recommend_mb(self) -> int:
        return self._config_int("pdf_optimize_recommend_mb", 250)

    def pdf_upload_block_mb(self) -> int:
        return self._config_int("pdf_upload_block_mb", 1000)

    def pdf_optimization_profile(self) -> str:
        profile = str(self.config_data.get("pdf_optimization_profile", "verlustfrei")).strip().lower()
        if profile not in {"verlustfrei", "standard", "maximal"}:
            return "verlustfrei"
        return profile

    def _config_int(self, key: str, default: int) -> int:
        try:
            return max(0, int(self.config_data.get(key, default) or default))
        except Exception:
            return default

    def _meipass_root(self) -> Path | None:
        try:
            return Path(sys._MEIPASS)
        except Exception:
            return None

    def _pdf_tool_search_roots(self) -> list[Path]:
        return _pmm_build_pdf_tool_search_roots(
            app_dir=APP_DIR,
            module_file=Path(__file__),
            executable=sys.executable,
            cwd=Path.cwd(),
            meipass_root=self._meipass_root(),
        )

    def pdf_size_mb(self, path: Path | None) -> float:
        return _pmm_pdf_size_mb(path)

    def format_file_size(self, path: Path | None) -> str:
        return _pmm_format_file_size(path)

    def format_size_bytes(self, size: int | float | str | None) -> str:
        return _pmm_format_size_bytes(size)

    def pdf_optimization_info_for_path(self, path: Path | None) -> dict:
        if not path:
            return {}
        item = self.item_for_local_path(path) or {}
        optimized_at = str(item.get("pdf_optimized_at") or "").strip()
        attempted_at = str(item.get("pdf_optimization_attempted_at") or "").strip()
        if not optimized_at and not attempted_at:
            return {}
        optimized_by = str(item.get("pdf_optimized_by") or item.get("edited_by") or item.get("uploaded_by") or "ODV").strip()
        return {
            "optimized_at": optimized_at,
            "attempted_at": attempted_at,
            "optimized_by": optimized_by,
            "original_size": item.get("pdf_original_size_bytes") or "",
            "optimized_size": item.get("pdf_optimized_size_bytes") or "",
            "tool": str(item.get("pdf_optimization_tool") or "").strip(),
            "profile": str(item.get("pdf_optimization_profile") or "").strip(),
            "result": str(item.get("pdf_optimization_result") or ("optimized" if optimized_at else "no_gain")).strip(),
        }

    def pdfa_path_for_document(self, path: Path | None) -> Path | None:
        return _pmm_pdfa_path_for_document(path)

    def ocr_path_for_document(self, path: Path | None) -> Path | None:
        return _pmm_ocr_path_for_document(path)

    def is_linked_pdfa_file_path(self, path: Path) -> bool:
        return _pmm_is_linked_pdfa_file_path(path)

    def pdf_display_prefix(self, path: Path) -> str:
        return _pmm_pdf_display_prefix(path, self.pdf_optimize_recommend_mb())

    def pdf_tree_tags(self, path: Path) -> tuple[str, ...]:
        return _pmm_pdf_tree_tags(path, self.pdf_optimize_recommend_mb())

    def visible_pdf_work_file(self, path: Path) -> bool:
        """Im Baum wird regulär nur die Arbeitsfassung gezeigt."""
        return _pmm_visible_pdf_work_file(path)

    def linked_pdf_paths_for_item(self, item: dict | None, document_path: Path | None = None) -> dict[str, Path | None]:
        path = document_path or self.resolve_document_local_path(item or {})
        ocr_path = None
        if item:
            ocr_text = str(item.get("ocr_pdf_path") or item.get("ocr_current_path") or "").strip()
            if ocr_text:
                candidate = Path(ocr_text)
                if candidate.exists():
                    ocr_path = candidate
        if not ocr_path:
            ocr_candidate = self.ocr_path_for_document(path)
            if ocr_candidate and ocr_candidate.exists():
                ocr_path = ocr_candidate
        pdfa_path = None
        pdfa_candidate = self.pdfa_path_for_document(path)
        if pdfa_candidate and pdfa_candidate.exists():
            pdfa_path = pdfa_candidate
        return {"work": path, "pdfa": pdfa_path, "ocr": ocr_path}

    def keep_pdf_overview_front(self, parent=None) -> None:
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

    def run_pdf_processing_dialog(self, title: str, text: str, worker, finish, parent=None) -> None:
        dialog = tk.Toplevel(parent or self)
        dialog.title(title)
        dialog.transient(parent or self)
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
        self.keep_pdf_overview_front(dialog)

        def run() -> None:
            try:
                result = worker()
                self.after(0, lambda result=result: close_and_finish(result=result, error=None))
            except Exception as exc:
                self.after(0, lambda error=exc: close_and_finish(result=None, error=error))

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

    def open_linked_pdfa_for_current_file(self, path: Path | None = None) -> None:
        source = path or self.file_view_current_path
        pdfa = self.pdfa_path_for_document(source)
        if not pdfa or not pdfa.exists():
            messagebox.showwarning("PDF/A", "Zu dieser Datei wurde keine PDF/A-Fassung gefunden.")
            return
        self.open_file_with_default_app(pdfa)

    def pdf_action_stub(self, action: str, path: Path | None = None, parent=None) -> None:
        self.keep_pdf_overview_front(parent)
        source = path or self.file_view_current_path
        if not source or source.suffix.lower() != ".pdf":
            messagebox.showwarning("PDF", "Bitte eine PDF-Datei auswählen.", parent=parent)
            self.keep_pdf_overview_front(parent)
            return
        if action == "PDF optimieren":
            info = self.pdf_optimization_info_for_path(source)
            if info:
                timestamp = info.get("optimized_at") or info.get("attempted_at") or "unbekannt"
                result_hint = "optimiert" if info.get("optimized_at") else "ohne kleinere Datei geprüft"
                detail = f"Dieses PDF wurde bereits am {timestamp} durch {info['optimized_by']} {result_hint}."
                if self.is_current_admin():
                    if not messagebox.askyesno("PDF optimieren", f"{detail}\nErneute Optimierung kann Qualität verschlechtern.\n\nTrotzdem erneut optimieren?", parent=parent):
                        self.keep_pdf_overview_front(parent)
                        return
                else:
                    messagebox.showwarning("PDF optimieren", f"{detail}\nKeine weitere Optimierung möglich.", parent=parent)
                    self.keep_pdf_overview_front(parent)
                    return
            self.optimize_pdf_file(source, parent=parent)
            return
        if action == "PDF/A erzeugen":
            self.create_pdfa_file(source, parent=parent)
            return
        messagebox.showinfo(
            "PDF",
            f"{action} ist vorbereitet, aber die eigentliche Verarbeitung wird im nächsten Schritt angebunden.\n\nDatei:\n{source}",
            parent=parent,
        )
        self.keep_pdf_overview_front(parent)

    def find_ghostscript_command(self) -> list[str] | None:
        return _pmm_find_ghostscript_command(self._pdf_tool_search_roots())

    def ensure_ghostscript_on_startup(self) -> None:
        if self.find_ghostscript_command():
            app_log("info", "Ghostscript ist verfügbar")
            return
        installer = self.find_bundled_ghostscript_installer()
        if not installer:
            app_log("warning", "Ghostscript nicht verfügbar und kein mitgelieferter Installer gefunden")
            return
        try:
            app_log("info", "Mitgelieferten Ghostscript-Installer starten", installer=str(installer))
            self.install_bundled_ghostscript(installer)
            if self.find_ghostscript_command():
                app_log("info", "Ghostscript wurde erfolgreich eingerichtet", installer=str(installer))
                try:
                    self.after(0, lambda: self.nextcloud_status_var.set(f"{self.nextcloud_status_var.get()} | Ghostscript: installiert"))
                except Exception:
                    pass
            else:
                app_log("warning", "Ghostscript-Installer wurde ausgeführt, Ghostscript danach aber nicht gefunden", installer=str(installer))
        except OSError as exc:
            win_error = None
            try:
                win_error = exc.winerror
            except Exception:
                pass
            if win_error == 740:
                try:
                    if self.run_ghostscript_installer_elevated(installer):
                        app_log("info", "Ghostscript-Installer erfordert erhöhte Rechte und wurde per UAC gestartet", installer=str(installer))
                        try:
                            self.after(0, lambda: self.nextcloud_status_var.set(f"{self.nextcloud_status_var.get()} | Ghostscript: UAC-Installation gestartet"))
                        except Exception:
                            pass
                        return
                except Exception as elevated_exc:
                    app_log_exception("Ghostscript-Installer konnte nicht erhöht gestartet werden", elevated_exc, installer=str(installer))
                    return
            app_log_exception("Mitgeliefertes Ghostscript konnte nicht automatisch installiert werden", exc, installer=str(installer))
        except Exception as exc:
            app_log_exception("Mitgeliefertes Ghostscript konnte nicht automatisch installiert werden", exc, installer=str(installer))

    def ghostscript_executable_candidates(self) -> list[Path]:
        return _pmm_ghostscript_executable_candidates(self._pdf_tool_search_roots())

    def ghostscript_installer_candidates(self) -> list[Path]:
        return _pmm_ghostscript_installer_candidates(self._pdf_tool_search_roots())

    def find_bundled_ghostscript_installer(self) -> Path | None:
        return _pmm_find_bundled_ghostscript_installer(self._pdf_tool_search_roots())

    def install_bundled_ghostscript(self, installer: Path) -> None:
        _pmm_install_bundled_ghostscript(installer=installer, app_dir=APP_DIR)

    def run_ghostscript_installer_elevated(self, installer: Path) -> bool:
        return _pmm_run_ghostscript_installer_elevated(installer=installer, app_dir=APP_DIR)

    def optimize_pdf_file(self, source: Path, parent=None) -> None:
        self.keep_pdf_overview_front(parent)
        if not self.ensure_local_pdf_available(source, parent=parent):
            return
        profile = self.pdf_optimization_profile()
        if not messagebox.askyesno(
            "PDF optimieren",
            f"PDF mit Optimierungsprofil '{profile}' optimieren?\n\nDatei:\n{source}\n\n"
            "ODV erstellt zuerst eine temporäre Datei und ersetzt die Arbeitsdatei nur, wenn die optimierte Datei kleiner ist.",
            parent=parent,
        ):
            self.keep_pdf_overview_front(parent)
            return
        temp = source.with_name(f"{source.stem}.__odv_optimized_tmp.pdf")
        original_size = source.stat().st_size
        display_name = self.display_name_var.get().strip() or "ODV"
        display_name = self._pdf_action_user_label()

        def worker() -> dict:
            if temp.exists():
                temp.unlink()
            tool = "pymupdf"
            if profile in {"standard", "maximal"}:
                gs = self.find_ghostscript_command()
                if gs:
                    self.run_ghostscript_pdf_optimization(source, temp, gs, profile)
                    tool = "ghostscript"
                else:
                    self.run_lossless_pdf_optimization(source, temp, profile)
            else:
                self.run_lossless_pdf_optimization(source, temp, profile)
            optimized_size = temp.stat().st_size if temp.exists() else 0
            if optimized_size <= 0:
                raise RuntimeError("Optimierte PDF-Datei wurde nicht erstellt.")
            if optimized_size >= original_size:
                try:
                    temp.unlink()
                except Exception:
                    pass
                self.record_pdf_optimization_attempt(source, original_size, optimized_size, tool, profile, display_name=display_name)
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
            self.record_pdf_optimization(source, original_size, optimized_size, tool, profile, display_name=display_name)
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
                self.keep_pdf_overview_front(parent)
                return
            self.refresh_pdf_views_after_action()
            if not result.get("changed"):
                messagebox.showinfo(
                    "PDF optimieren",
                    "Die PDF-Optimierung hat keine kleinere Datei ergeben.\n"
                    f"Arbeitsdatei bleibt unverändert: {self.format_size_bytes(result.get('original_size'))}\n\n"
                    "Der Optimierungsversuch wird in der PDF-Übersicht mit X dokumentiert.",
                    parent=parent,
                )
                self.keep_pdf_overview_front(parent)
                return
            saved = int(result.get("original_size") or 0) - int(result.get("optimized_size") or 0)
            messagebox.showinfo(
                "PDF optimieren",
                f"PDF wurde mit Profil '{profile}' optimiert.\n\n"
                f"Vorher: {self.format_size_bytes(result.get('original_size'))}\n"
                f"Nachher: {self.format_size_bytes(result.get('optimized_size'))}\n"
                f"Ersparnis: {self.format_size_bytes(saved)}\n\n"
                "Die Änderung wird über den Nextcloud-Sync hochgeladen.",
                parent=parent,
            )
            self.keep_pdf_overview_front(parent)

        self.run_pdf_processing_dialog(
            "PDF optimieren",
            f"Datei wird verarbeitet...\n\n{source.name}",
            worker,
            finish,
            parent=parent,
        )

    def run_lossless_pdf_optimization(self, source: Path, target: Path, profile: str | None = None) -> None:
        if importlib.util.find_spec("fitz") is None:
            raise RuntimeError("PyMuPDF ist nicht verfügbar. Verlustfreie PDF-Optimierung kann nicht ausgeführt werden.")
        import fitz

        selected_profile = (profile or self.pdf_optimization_profile()).strip().lower()
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

    def run_ghostscript_pdf_optimization(self, source: Path, target: Path, gs_command: list[str], profile: str) -> None:
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

    def create_pdfa_file(self, source: Path, parent=None) -> None:
        self.keep_pdf_overview_front(parent)
        if not self.ensure_local_pdf_available(source, parent=parent):
            return
        target = self.pdfa_path_for_document(source)
        if not target:
            messagebox.showwarning("PDF/A", "Bitte eine PDF-Datei auswählen.", parent=parent)
            self.keep_pdf_overview_front(parent)
            return
        if target.exists():
            messagebox.showinfo("PDF/A", f"PDF/A-Fassung ist bereits vorhanden:\n{target}", parent=parent)
            self.keep_pdf_overview_front(parent)
            return
        gs = self.find_ghostscript_command()
        if not gs:
            messagebox.showwarning(
                "PDF/A",
                "Ghostscript wurde nicht gefunden.\n\n"
                "PDF/A-Erzeugung wird erst aktiviert, wenn Ghostscript installiert bzw. im PATH verfügbar ist.",
                parent=parent,
            )
            self.keep_pdf_overview_front(parent)
            return
        if not messagebox.askyesno("PDF/A erzeugen", f"PDF/A-Archivfassung erzeugen?\n\nQuelle:\n{source}\n\nZiel:\n{target}", parent=parent):
            self.keep_pdf_overview_front(parent)
            return
        temp = target.with_name(f"{target.stem}.__odv_pdfa_tmp.pdf")
        display_name = self.display_name_var.get().strip() or "ODV"

        def worker() -> dict:
            if temp.exists():
                temp.unlink()
            self.run_ghostscript_pdfa(source, temp, gs)
            shutil.move(str(temp), str(target))
            self.record_pdfa_creation(source, target, gs[0], display_name=display_name)
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
                self.keep_pdf_overview_front(parent)
                return
            messagebox.showinfo(
                "PDF/A",
                f"PDF/A-Fassung wurde erzeugt:\n{target}\n\nDie Datei wird über den Nextcloud-Sync hochgeladen.",
                parent=parent,
            )
            self.refresh_pdf_views_after_action()
            self.keep_pdf_overview_front(parent)

        self.run_pdf_processing_dialog(
            "PDF/A erzeugen",
            f"Datei wird verarbeitet...\n\n{source.name}",
            worker,
            finish,
            parent=parent,
        )

    def run_ghostscript_pdfa(self, source: Path, target: Path, gs_command: list[str]) -> None:
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

    def ensure_local_pdf_available(self, source: Path, parent=None) -> bool:
        if source.exists() and source.is_file() and source.suffix.lower() == ".pdf":
            return True
        messagebox.showwarning(
            "PDF",
            "Diese PDF ist in Nextcloud vorgesehen, aber lokal nicht verfügbar.\n"
            "Bitte die Datei zuerst synchronisieren/herunterladen.",
            parent=parent,
        )
        self.keep_pdf_overview_front(parent)
        return False

    def record_pdf_optimization(self, source: Path, original_size: int, optimized_size: int, tool: str, profile: str, display_name: str | None = None) -> None:
        item, metadata_file = self.ensure_pdf_metadata_item(source)
        display_name = display_name or self._pdf_action_user_label()
        item["pdf_optimized_at"] = datetime.now().isoformat(timespec="seconds")
        item["pdf_optimization_attempted_at"] = item["pdf_optimized_at"]
        item["pdf_optimized_by"] = display_name
        item["pdf_original_size_bytes"] = original_size
        item["pdf_optimized_size_bytes"] = optimized_size
        item["pdf_optimization_tool"] = tool
        item["pdf_optimization_profile"] = profile
        item["pdf_optimization_result"] = "optimized"
        append_metadata_history(item, display_name, "PDF optimiert", f"{self.format_size_bytes(original_size)} -> {self.format_size_bytes(optimized_size)}; Werkzeug: {tool}; Profil: {profile}")
        save_metadata_file(metadata_file, item)

    def record_pdf_optimization_attempt(self, source: Path, original_size: int, attempted_size: int, tool: str, profile: str, display_name: str | None = None) -> None:
        item, metadata_file = self.ensure_pdf_metadata_item(source)
        display_name = display_name or self._pdf_action_user_label()
        now = datetime.now().isoformat(timespec="seconds")
        item["pdf_optimization_attempted_at"] = now
        item["pdf_optimized_by"] = display_name
        item["pdf_original_size_bytes"] = original_size
        item["pdf_optimized_size_bytes"] = attempted_size
        item["pdf_optimization_tool"] = tool
        item["pdf_optimization_profile"] = profile
        item["pdf_optimization_result"] = "no_gain"
        append_metadata_history(item, display_name, "PDF-Optimierung ohne Verkleinerung", f"{self.format_size_bytes(original_size)} -> {self.format_size_bytes(attempted_size)}; Werkzeug: {tool}; Profil: {profile}")
        save_metadata_file(metadata_file, item)
        item["_metadata_file"] = str(metadata_file)

    def record_pdfa_creation(self, source: Path, target: Path, tool: str, display_name: str | None = None) -> None:
        item, metadata_file = self.ensure_pdf_metadata_item(source)
        display_name = display_name or self._pdf_action_user_label()
        item["pdfa_path"] = str(target)
        item["pdfa_filename"] = target.name
        item["pdfa_created_at"] = datetime.now().isoformat(timespec="seconds")
        item["pdfa_created_by"] = display_name
        item["pdfa_tool"] = tool
        append_metadata_history(item, display_name, "PDF/A erzeugt", f"{source.name} -> {target.name}; Werkzeug: {tool}")
        save_metadata_file(metadata_file, item)
        item["_metadata_file"] = str(metadata_file)

    def ensure_pdf_metadata_item(self, source: Path) -> tuple[dict, Path]:
        item, metadata_file = self.ensure_file_view_metadata_item(source)
        self.file_view_metadata_by_path[str(source)] = item
        return item, metadata_file

    def refresh_pdf_views_after_action(self) -> None:
        try:
            self.refresh_file_view_tree()
        except Exception:
            pass

    def pdf_report_rows(self, root: Path | None = None) -> list[dict[str, str]]:
        base = Path(str(self.base_folder_var.get() or ""))
        scan_root = root or base
        if not base.exists() or not base.is_dir():
            return []
        if not scan_root.exists() or not scan_root.is_dir():
            return []
        if not self.file_view_metadata_by_path:
            try:
                self.file_view_metadata_items = load_metadata_files(self.metadata_folder_path())
                self.file_view_metadata_by_path = {
                    str(Path(str(item.get("current_path") or ""))): item
                    for item in self.file_view_metadata_items
                    if str(item.get("current_path") or "").strip()
                }
            except Exception:
                pass
        return _pmm_build_pdf_report_rows(
            base,
            scan_root,
            self.is_hidden_system_path,
            self.linked_pdf_paths_for_item,
            self.pdf_optimization_info_for_path,
            lambda path, links: self.pdf_is_non_searchable_text(path, has_linked_ocr=bool(links.get("ocr"))),
        )

    def write_pdf_size_log(self, rows: list[dict[str, str]] | None = None) -> Path:
        rows = rows if rows is not None else self.pdf_report_rows()
        return _pmm_write_pdf_size_log(rows, APP_DIR)

    def open_pdf_overview_dialog(self) -> None:
        if not self.is_current_admin():
            return
        base = Path(str(self.base_folder_var.get() or ""))
        root_options: list[tuple[str, Path]] = []
        if base.exists() and base.is_dir():
            root_options.append((str(base), base))
            try:
                for child in sorted([p for p in base.iterdir() if p.is_dir() and not self.is_hidden_system_path(p)], key=lambda p: p.name.lower()):
                    root_options.append((child.name, child))
            except Exception:
                pass
        dialog = tk.Toplevel(self)
        dialog.title("Übersicht PDF-Dateien")
        try:
            dialog.transient(self)
        except Exception:
            pass
        try:
            self.track_window_geometry(dialog, "Übersicht PDF-Dateien")
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
                    rows = self.pdf_report_rows(current_root)
                    if threshold:
                        rows = [row for row in rows if float(row.get("work_size_mb") or 0) > threshold]
                    rows.sort(key=lambda row: sort_key(row, current_sort), reverse=bool(current_descending))
                    try:
                        log_path = self.write_pdf_size_log(rows)
                    except Exception as exc:
                        app_log_exception("PDF-Größenlog konnte nicht geschrieben werden", exc)
                        log_path = None
                except Exception as exc:
                    app_log_exception("PDF-Übersicht konnte nicht geladen werden", exc)
                    rows = []
                    log_path = None

                    def apply_error() -> None:
                        if request_id != load_state["id"]:
                            return
                        status_var.set(f"PDF-Übersicht konnte nicht geladen werden ({exc})")
                    self.after(0, apply_error)
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

                self.after(0, apply)

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
            item = self.item_for_local_path(path) or {}
            linked = self.linked_pdf_paths_for_item(item, path)
            menu = tk.Menu(dialog, tearoff=False)
            menu.add_command(label="Datei öffnen", command=lambda: self.open_file_with_default_app(path))
            menu.add_command(label="Download / Kopie speichern unter...", command=lambda: self.download_file_to_local_folder(path, item))
            if linked.get("ocr"):
                menu.add_command(label="OCR anzeigen", command=lambda p=linked["ocr"]: self.open_file_with_default_app(p))
            elif self.find_pdf_ocr_backend():
                menu.add_command(
                    label="PDF OCR erstellen...",
                    command=lambda: self.create_ocr_for_document_path(path, item, on_success=populate),
                )
            if linked.get("pdfa"):
                menu.add_command(label="Original / PDF-A anzeigen", command=lambda p=linked["pdfa"]: self.open_file_with_default_app(p))
            menu.add_separator()
            menu.add_command(label="PDF optimieren...", command=lambda: self.pdf_action_stub("PDF optimieren", path, parent=dialog))
            if linked.get("pdfa"):
                menu.add_command(label="PDF/A bereits vorhanden", state="disabled")
            else:
                menu.add_command(label="PDF/A erzeugen...", command=lambda: self.pdf_action_stub("PDF/A erzeugen", path, parent=dialog))
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
