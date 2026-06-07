from __future__ import annotations

from pathlib import Path
from datetime import datetime
import threading
import re
import tkinter as tk
from tkinter import ttk, messagebox

from .app_logging import app_log_exception
from .config import OPENAI_DEFAULT_MODEL, OPENAI_MODEL_OPTIONS
from .file_service import append_metadata_history, unique_path_with_counter
from .openai_client import OpenAIClient, OpenAIError
from .postprocess_place_utils import (
    admin_place_names_for_scan as _ppm_admin_place_names_for_scan,
    clean_place_context_text as _ppm_clean_place_context_text,
    compact_openai_place_contexts as _ppm_compact_openai_place_contexts,
    place_context_counts as _ppm_place_context_counts,
    find_place_contexts_in_text as _ppm_find_place_contexts_in_text,
)
from .postprocess_openai_utils import (
    openai_cached_model_result as _ppm_openai_cached_model_result,
    openai_used_models as _ppm_openai_used_models,
    store_openai_model_result as _ppm_store_openai_model_result,
)


class PostprocessManagerMixin:
    """OpenAI-, OCR- und Nachbearbeitungshelfer für die zentrale Dateiliste."""

    _OPENAI_SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".log", ".docx", ".odt"}
    _OPENAI_FALLBACK_MODELS = OPENAI_MODEL_OPTIONS

    def _read_int_config(self, key: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
        try:
            value = int(self.config_data.get(key, default))
        except Exception:
            return default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def _openai_default_model(self) -> str:
        return str(self.config_data.get("openai_model", OPENAI_DEFAULT_MODEL) or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL

    def _openai_client_for_model(self, model_name: str, warning_title: str = "OpenAI") -> OpenAIClient | None:
        key = str(self.config_data.get("openai_api_key", "") or "").strip()
        if not key:
            messagebox.showwarning(warning_title, f"{warning_title} ist nicht konfiguriert.")
            return None
        return OpenAIClient(api_key=key, model=(str(model_name or "").strip() or OPENAI_DEFAULT_MODEL))

    def _resolve_openai_model_dialog_result(
        self,
        item: dict,
        result_field: str,
        legacy_model_field: str,
        previous_time_field: str,
        used_fallback: bool,
        accept_label: str,
        title_with_fallback: str,
        title_without: str,
        intro_with_fallback: str,
        intro_without: str,
        list_text_getter,
    ) -> str:
        used_models = self.openai_used_models(item, result_field, legacy_model_field)
        previous_model = ", ".join(used_models)
        previous_time = str(item.get(previous_time_field) or "").strip() or "-"
        model_values = self._openai_model_options(item, result_field, legacy_model_field)
        current_model = self._openai_default_model()

        dialog = tk.Toplevel(self)
        dialog.title(title_with_fallback if used_fallback else title_without)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("560x470")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        if used_fallback:
            intro = intro_with_fallback
            list_text = "Keine Ortsfundstellen."
        else:
            intro = intro_without
            list_text = list_text_getter()

        ttk.Label(dialog, text=f"{intro}", wraplength=520).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        model_frame = ttk.Frame(dialog)
        model_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        model_frame.columnconfigure(1, weight=1)
        ttk.Label(model_frame, text="OpenAI-Modell:").grid(row=0, column=0, sticky="w")
        model_var = tk.StringVar(value=current_model)
        ttk.Combobox(model_frame, textvariable=model_var, values=model_values, state="readonly", width=28).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(dialog, text=f"Bisherig verwendet: {previous_model}").grid(row=2, column=0, sticky="w", padx=12)
        ttk.Label(dialog, text=f"Letzter Stand: {previous_time}").grid(row=3, column=0, sticky="w", padx=12)
        info_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=info_var, foreground="#555555", wraplength=520).grid(row=4, column=0, sticky="w", padx=12, pady=(4, 0))
        text = tk.Text(dialog, height=12, wrap="word")
        text.grid(row=2, column=0, sticky="nsew", padx=12, pady=4)
        text.insert("1.0", list_text)
        text.configure(state="disabled")
        result = {"model": ""}

        def accept() -> None:
            result["model"] = model_var.get().strip()
            dialog.destroy()

        def refresh_info(*_args) -> None:
            selected = model_var.get().strip()
            cached = bool(self.openai_cached_model_result(item, selected, result_field))
            if cached:
                info_var.set(f"Dieses Dokument wurde mit diesem Modell bereits verarbeitet ({previous_time}). Gespeicherte Vorschläge werden angezeigt.")
                continue_button.configure(text="Gespeicherte Vorschläge anzeigen", state="normal")
            else:
                info_var.set("OpenAI startet erst nach Bestätigung und verursacht Kosten.")
                continue_button.configure(text=accept_label, state="normal")

        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, sticky="e", padx=12, pady=(8, 12))
        continue_button = ttk.Button(buttons, text=accept_label, command=accept)
        continue_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
        model_var.trace_add("write", refresh_info)
        refresh_info()
        self.wait_window(dialog)
        return result["model"]

    def _openai_model_options(self, item: dict, result_field: str, legacy_field: str) -> list[str]:
        current_model = self._openai_default_model()
        used_models = self.openai_used_models(item, result_field, legacy_field)
        model_values: list[str] = []
        for model in (current_model, *self._OPENAI_FALLBACK_MODELS):
            if model and model not in model_values:
                model_values.append(model)
        for model in used_models:
            if model and model not in model_values:
                model_values.append(model)
        return model_values

    @staticmethod
    def _choose_openai_action(row_vars: dict[str, tk.BooleanVar], selected_action: str) -> None:
        if not row_vars.get(selected_action) or not row_vars[selected_action].get():
            return
        for action_name, var in row_vars.items():
            if action_name != selected_action:
                var.set(False)

    @staticmethod
    def _readonly_text_widget(parent: tk.Widget, value: str, width: int, height: int, background_source: tk.Widget | None = None) -> tk.Text:
        source = background_source or parent
        source_background = ""
        if source is not None:
            source_background = source.cget("background")
        text_widget = tk.Text(
            parent,
            width=width,
            height=height,
            wrap="word",
            relief="flat",
            borderwidth=0,
            background=source_background,
            font=("TkDefaultFont", 9),
        )
        text_widget.insert("1.0", value or "-")
        text_widget.configure(state="disabled")
        return text_widget

    @staticmethod
    def _openai_display_height(value: str, wrap_at: int = 55, max_lines: int = 10, fallback: int = 1) -> int:
        text = str(value or "")
        line_count = max(fallback, len(text.splitlines()))
        estimated_wrap_lines = max(fallback, (len(text) + max(1, wrap_at - 1)) // max(1, wrap_at))
        return min(max_lines, max(line_count, estimated_wrap_lines))

    def existing_ocr_pdf_for_path(self, path: Path | None) -> Path | None:
        if path is None or path.suffix.lower() != ".pdf":
            return None
        exact = path.with_name(f"{path.stem}_ocr.pdf")
        if exact.exists() and exact.is_file():
            return exact
        candidates = [candidate for candidate in path.parent.glob(f"{path.stem}_ocr_#*.pdf") if candidate.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)

    def admin_selected_document_path(self) -> Path | None:
        path = self.file_view_current_path
        if path is not None and path.exists() and path.is_file():
            return path
        item = self.selected_admin_upload()
        if not item:
            return None
        return self.resolve_document_local_path(item)

    def update_admin_openai_controls(self) -> None:
        path = self.admin_selected_document_path()
        for button in (
            self.admin_openai_button,
            self.admin_openai_places_button,
            self.admin_place_contexts_button,
            self.admin_ocr_pdf_button,
        ):
            button.grid_remove()
        if path is None or not path.exists() or not path.is_file():
            self.admin_openai_status_var.set("OpenAI: keine Datei ausgewählt")
            return
        suffix = path.suffix.lower()
        if suffix not in self._OPENAI_SUPPORTED_SUFFIXES:
            self.admin_openai_status_var.set("OpenAI: Datei ist kein lesbares Textdokument/PDF")
            return
        analysis_path = self.existing_ocr_pdf_for_path(path) or path
        sample = self.extract_upload_text_sample(analysis_path, max_chars=500, max_pdf_pages=2)
        item = self.selected_admin_upload() or {}
        can_edit = self.can_edit_file_view_metadata(path, item)
        contexts_button = self.admin_place_contexts_button
        contexts_available = bool(item.get("openai_place_contexts"))
        if contexts_available:
            contexts_button.grid()
            contexts_button.configure(state="normal")
        if sample:
            self.admin_openai_button.grid()
            self.admin_openai_button.configure(state=("normal" if can_edit else "disabled"))
            self.admin_openai_places_button.grid()
            self.admin_openai_places_button.configure(state=("normal" if can_edit else "disabled"))
            if self.existing_ocr_pdf_for_path(path):
                self.admin_openai_status_var.set("OpenAI: OCR-PDF vorhanden und lesbar")
            else:
                self.admin_openai_status_var.set("OpenAI: Text lokal lesbar")
        elif suffix == ".pdf":
            self.admin_ocr_pdf_button.grid()
            self.admin_ocr_pdf_button.configure(state=("normal" if can_edit else "disabled"))
            self.admin_openai_status_var.set("OpenAI: PDF ohne lesbaren Text - bitte PDF OCR erstellen")
        else:
            self.admin_openai_status_var.set("OpenAI: Inhalt lokal nicht lesbar")

    def admin_create_ocr_for_selected_document(self) -> None:
        item = self.selected_admin_upload()
        path = self.admin_selected_document_path()
        if not item or path is None or path.suffix.lower() != ".pdf":
            messagebox.showwarning("PDF OCR", "Bitte zuerst ein PDF-Dokument auswählen.")
            return
        ocr_backend = self.find_pdf_ocr_backend()
        if not ocr_backend:
            messagebox.showerror("PDF OCR", "Es wurde kein PDF-OCR-Werkzeug gefunden.")
            return
        target = unique_path_with_counter(path.with_name(f"{path.stem}_ocr.pdf"))
        self.admin_openai_status_var.set("PDF OCR läuft ...")
        self.admin_ocr_pdf_button.configure(state="disabled")

        def run() -> None:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                backend_name, backend_config = ocr_backend
                if backend_name == "pymupdf":
                    self._run_pdf_ocr_with_pymupdf(path, target, backend_config)
                else:
                    self._run_pdf_ocr_with_ocrmypdf(path, target, backend_config)

                def finish() -> None:
                    item["ocr_pdf_path"] = str(target)
                    item["ocr_pdf_filename"] = target.name
                    item["ocr_source_filename"] = path.name
                    item["ocr_created_at"] = datetime.now().isoformat(timespec="seconds")
                    append_metadata_history(item, self.display_name_var.get().strip() or "Admin", "PDF OCR erstellt", target.name)
                    self.save_item_to_api(item)
                    self.save_item_json_if_present(item)
                    if path.suffix.lower() == ".pdf":
                        self.file_view_current_metadata = item
                        self.load_file_view_metadata_form()
                    self.update_admin_openai_controls()
                    self.admin_openai_status_var.set("PDF OCR fertig - OpenAI kann jetzt prüfen")
                    messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt:\n{target}")

                self.after(0, finish)
            except Exception as exc:
                app_log_exception("Admin-PDF-OCR konnte nicht ausgeführt werden", exc, source=str(path), target=str(target))
                self.after(0, lambda: self.admin_openai_status_var.set("PDF OCR fehlgeschlagen"))
                self.after(0, lambda: messagebox.showerror("PDF OCR", f"OCR konnte nicht ausgeführt werden:\n{exc}"))
                self.after(0, self.update_admin_openai_controls)

        threading.Thread(target=run, daemon=True).start()

    def create_ocr_for_document_path(self, path: Path | None, item: dict | None = None, on_success=None) -> None:
        """Erzeugt OCR für eine einzelne PDF-Datei und verknüpft sie optional mit einem Datensatz."""
        if path is None or path.suffix.lower() != ".pdf":
            messagebox.showwarning("PDF OCR", "Bitte zuerst ein PDF-Dokument auswählen.")
            return
        ocr_backend = self.find_pdf_ocr_backend()
        if not ocr_backend:
            messagebox.showerror("PDF OCR", "Es wurde kein PDF-OCR-Werkzeug gefunden.")
            return
        item = item if isinstance(item, dict) else (self.item_for_local_path(path) or None)
        source = path
        target = unique_path_with_counter(source.with_name(f"{source.stem}_ocr.pdf"))

        def run() -> None:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                backend_name, backend_config = ocr_backend
                if backend_name == "pymupdf":
                    self._run_pdf_ocr_with_pymupdf(source, target, backend_config)
                else:
                    self._run_pdf_ocr_with_ocrmypdf(source, target, backend_config)

                if item is not None:
                    item["ocr_pdf_path"] = str(target)
                    item["ocr_pdf_filename"] = target.name
                    item["ocr_source_filename"] = source.name
                    item["ocr_created_at"] = datetime.now().isoformat(timespec="seconds")
                    append_metadata_history(item, self.display_name_var.get().strip() or "Admin", "PDF OCR erstellt", f"{source.name} → {target.name}")
                    if str(source) in self.file_view_metadata_by_path:
                        self.file_view_metadata_by_path[str(source)] = item
                    if self.file_view_current_path == source:
                        self.file_view_current_metadata = item
                    metadata_file = str(item.get("_metadata_file") or "").strip()
                    if metadata_file and not item.get("_pending_existing_file_metadata"):
                        try:
                            self.save_file_view_item_to_storage(item, Path(metadata_file), False)
                        except Exception:
                            pass

                if on_success:
                    self.after(0, on_success)
                self.after(0, lambda: messagebox.showinfo("PDF OCR", f"Durchsuchbares PDF wurde erstellt:\n{target}"))
            except Exception as exc:
                app_log_exception("PDF-OCR konnte nicht ausgeführt werden", exc, source=str(source), target=str(target))
                self.after(
                    0,
                    lambda: messagebox.showerror("PDF OCR", f"PDF OCR konnte nicht ausgeführt werden:\n{exc}"),
                )

        threading.Thread(target=run, daemon=True).start()

    def admin_openai_selected_document(self) -> None:
        item = self.selected_admin_upload()
        path = self.admin_selected_document_path()
        if not item or path is None:
            return
        selected_model = self.choose_admin_openai_model(item)
        if not selected_model:
            return
        cached = self.openai_cached_model_result(item, selected_model, "openai_model_results")
        if cached:
            suggestions = cached.get("suggestions") if isinstance(cached.get("suggestions"), dict) else {}
            usage_text = str(cached.get("usage_text") or f"gespeichertes Ergebnis ({selected_model})")
            self.apply_admin_openai_metadata_suggestions(item, suggestions, selected_model, usage_text, cached=True)
            self.update_admin_openai_controls()
            return
        analysis_path = self.existing_ocr_pdf_for_path(path) or path
        sample = self.extract_upload_text_sample(analysis_path, max_chars=self.openai_text_sample_chars(), max_pdf_pages=self.openai_pdf_sample_pages())
        if not sample and path.suffix.lower() == ".pdf":
            messagebox.showwarning("OpenAI", "Dieses PDF ist lokal nicht lesbar. Bitte zuerst PDF OCR erstellen.")
            self.update_admin_openai_controls()
            return
        client = self._openai_client_for_model(selected_model, warning_title="OpenAI")
        if client is None:
            return
        self.admin_openai_button.configure(state="disabled")
        self.admin_openai_status_var.set(f"OpenAI prüft mit {selected_model} ...")

        def run() -> None:
            try:
                result = client.analyze_upload_file(filename=path.name, extension=path.suffix.lower(), sample=sample)
                metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
                local_metadata = self.derive_metadata_from_text(filename=path.name, extension=path.suffix.lower(), sample=sample)
                merged = dict(local_metadata)
                for key, value in metadata.items():
                    if str(value or "").strip():
                        merged[key] = value
                usage_text = self.format_openai_usage(result.get("usage", {}), model_name=client.model)
                self.store_openai_model_result(item, client.model, "openai_model_results", {
                    "suggestions": merged,
                    "usage_text": usage_text,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })

                def apply() -> None:
                    self.apply_admin_openai_metadata_suggestions(item, merged, client.model, usage_text, cached=False)
                    self.update_admin_openai_controls()

                self.after(0, apply)
            except OpenAIError as exc:
                self.after(0, lambda: self.admin_openai_status_var.set(f"OpenAI: {exc.user_message()}"))
                self.after(0, self.update_admin_openai_controls)
            except Exception as exc:
                app_log_exception("Admin-OpenAI-Prüfung fehlgeschlagen", exc, path=str(path))
                self.after(0, lambda: self.admin_openai_status_var.set("OpenAI-Fehler"))
                self.after(0, self.update_admin_openai_controls)

        threading.Thread(target=run, daemon=True).start()

    def openai_cached_model_result(self, item: dict, model: str, field: str) -> dict:
        return _ppm_openai_cached_model_result(item, model, field)

    def store_openai_model_result(self, item: dict, model: str, field: str, data: dict) -> None:
        _ppm_store_openai_model_result(item, model, field, data)

    def openai_used_models(self, item: dict, field: str, legacy_model_field: str = "") -> list[str]:
        return _ppm_openai_used_models(item, field, legacy_model_field)

    def apply_admin_openai_metadata_suggestions(self, item: dict, suggestions: dict, model_name: str, usage_text: str, cached: bool = False) -> None:
        changed = self.show_admin_openai_apply_dialog(suggestions)
        if changed is None:
            self.admin_openai_status_var.set(f"OpenAI: Vorschläge nicht übernommen | {usage_text}")
            return
        previous_fields = [str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()]
        item["openai_metadata_fields"] = list(dict.fromkeys(previous_fields + changed))
        item["openai_metadata_model"] = model_name
        item["openai_metadata_applied_at"] = datetime.now().isoformat(timespec="seconds")
        details = f"Modell: {model_name}"
        details += "; gespeichertes Ergebnis verwendet" if cached else "; neues Ergebnis gespeichert"
        details += f"; Felder: {', '.join(changed)}" if changed else "; keine Felder übernommen"
        append_metadata_history(item, self.display_name_var.get().strip() or "Admin", "OpenAI-Metadaten geprüft", details)
        if changed:
            self.persist_admin_openai_form_item(item)
            api_ok, api_msg = self.save_admin_openai_item_to_storage(item)
            self.update_admin_tree_row_for_item(item)
            if api_ok:
                self.admin_openai_status_var.set(f"OpenAI: {len(changed)} Feld(er) übernommen und gespeichert | {usage_text}")
            else:
                self.admin_openai_status_var.set(f"OpenAI: lokal übernommen; MySQL nicht gespeichert: {api_msg} | {usage_text}")
        else:
            api_ok, api_msg = self.save_admin_openai_item_to_storage(item)
            if api_ok:
                self.update_admin_tree_row_for_item(item)
                self.admin_openai_status_var.set(f"OpenAI: Modell geprüft, keine Felder übernommen | {usage_text}")
            else:
                self.admin_openai_status_var.set(f"OpenAI: Modell lokal markiert; MySQL nicht gespeichert: {api_msg} | {usage_text}")

    def admin_place_names_for_scan(self) -> list[str]:
        try:
            current = self.place_var.get().strip()
        except Exception:
            current = ""
        return _ppm_admin_place_names_for_scan(self.place_folder_map, current)

    def find_place_contexts_in_text(self, text: str, places: list[str], context_chars: int = 650, max_contexts: int = 30) -> list[dict[str, str]]:
        return _ppm_find_place_contexts_in_text(text, places, context_chars=context_chars, max_contexts=max_contexts)

    def clean_place_context_text(self, text: str) -> str:
        return _ppm_clean_place_context_text(text)

    def admin_openai_place_scan_selected_document(self) -> None:
        item = self.selected_admin_upload()
        path = self.admin_selected_document_path()
        if not item or path is None:
            return
        places = self.admin_place_names_for_scan()
        if not places:
            messagebox.showwarning("Orte prüfen", "Keine Orte aus der Ortsverwaltung gefunden.")
            return
        analysis_path = self.existing_ocr_pdf_for_path(path) or path
        local_scan_text = self.extract_upload_text_sample(
            analysis_path,
            max_chars=10_000_000,
            max_pdf_pages=10_000,
        )
        if not local_scan_text and path.suffix.lower() == ".pdf":
            messagebox.showwarning("Orte prüfen", "Dieses PDF ist lokal nicht lesbar. Bitte zuerst PDF OCR erstellen.")
            self.update_admin_openai_controls()
            return
        place_context_chars = self._read_int_config("openai_place_context_chars", 650, minimum=100, maximum=6000)
        place_max_contexts = self._read_int_config("openai_place_max_contexts", 30, minimum=1, maximum=200)
        contexts = self.find_place_contexts_in_text(local_scan_text or "", places, context_chars=place_context_chars, max_contexts=place_max_contexts)
        fallback_text = ""
        if not contexts:
            fallback_text = self.extract_upload_text_sample(analysis_path, max_chars=self.openai_text_sample_chars(), max_pdf_pages=self.openai_pdf_sample_pages()) or ""
            selected_model = self.confirm_admin_place_scan_openai(item, contexts, used_fallback=True)
            if not selected_model:
                self.admin_openai_status_var.set("Orte prüfen: kein Ort lokal gefunden - OpenAI nicht gestartet")
                return
        else:
            selected_model = self.confirm_admin_place_scan_openai(item, contexts, used_fallback=False)
        if not selected_model:
            found_places = ", ".join(self.place_context_counts(contexts).keys())
            self.admin_openai_status_var.set(f"Orte prüfen: lokal gefunden ({found_places}) - OpenAI nicht gestartet")
            return
        cached = self.openai_cached_model_result(item, selected_model, "openai_place_model_results")
        if cached:
            result = cached.get("result") if isinstance(cached.get("result"), dict) else {}
            cached_contexts = cached.get("contexts") if isinstance(cached.get("contexts"), list) else contexts
            usage_text = str(cached.get("usage_text") or f"gespeichertes Ergebnis ({selected_model})")
            self.show_admin_place_scan_result_dialog(
                item,
                result,
                cached_contexts,
                usage_text,
                used_fallback=bool(cached.get("used_fallback", not bool(cached_contexts))),
                model_name=selected_model,
            )
            self.update_admin_openai_controls()
            return
        client = self._openai_client_for_model(selected_model, warning_title="OpenAI")
        if client is None:
            return
        self.admin_openai_places_button.configure(state="disabled")
        if contexts:
            self.admin_openai_status_var.set(f"Orte prüfen: {len(contexts)} Fundstelle(n), OpenAI läuft ...")
        else:
            self.admin_openai_status_var.set("Orte prüfen: kein Ort lokal gefunden, begrenzte Textprobe wird geprüft ...")

        def run() -> None:
            try:
                result = client.analyze_place_contexts(path.name, contexts, fallback_text=fallback_text, max_context_chars=(place_context_chars * 2 + 80))
                usage_text = self.format_openai_usage(result.get("usage", {}), model_name=client.model)
                self.store_openai_model_result(item, client.model, "openai_place_model_results", {
                    "result": result,
                    "contexts": self.compact_openai_place_contexts(contexts),
                    "usage_text": usage_text,
                    "used_fallback": not bool(contexts),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })

                def apply() -> None:
                    self.show_admin_place_scan_result_dialog(
                        item,
                        result,
                        contexts,
                        usage_text,
                        used_fallback=not bool(contexts),
                        model_name=client.model,
                    )
                    self.update_admin_openai_controls()

                self.after(0, apply)
            except OpenAIError as exc:
                self.after(0, lambda: self.admin_openai_status_var.set(f"Orte prüfen: {exc.user_message()}"))
                self.after(0, self.update_admin_openai_controls)
            except Exception as exc:
                app_log_exception("Admin-OpenAI-Ortsprüfung fehlgeschlagen", exc, path=str(path))
                self.after(0, lambda: self.admin_openai_status_var.set("Orte prüfen: OpenAI-Fehler"))
                self.after(0, self.update_admin_openai_controls)

        threading.Thread(target=run, daemon=True).start()

    def place_context_counts(self, contexts: list[dict[str, str]]) -> dict[str, int]:
        return _ppm_place_context_counts(contexts)

    def confirm_admin_place_scan_openai(self, item: dict, contexts: list[dict[str, str]], used_fallback: bool = False) -> str:
        if used_fallback:
            intro = (
                "Es wurde kein Ort aus der Ortsverwaltung im lokal lesbaren Text gefunden.\n\n"
                "Soll OpenAI stattdessen mit der begrenzten Textprobe nach den OpenAI-Einstellungen fortfahren?"
            )
            list_text = "Keine Ortsfundstellen."
        else:
            counts = self.place_context_counts(contexts)
            intro = (
                f"ODV hat lokal {len(contexts)} Fundstelle(n) zu {len(counts)} Ort(en) gefunden.\n\n"
                "Soll OpenAI mit diesen Fundstellen-Kontexten fortfahren?"
            )
            list_text = "\n".join(f"{place}: {count} Fundstelle(n)" for place, count in counts.items())
        return self._resolve_openai_model_dialog_result(
            item=item,
            result_field="openai_place_model_results",
            legacy_model_field="openai_place_contexts_model",
            previous_time_field="openai_place_contexts_updated_at",
            used_fallback=used_fallback,
            accept_label="Mit OpenAI fortfahren",
            title_with_fallback="Keine Orte lokal gefunden",
            title_without="Orte lokal gefunden",
            intro_with_fallback=intro,
            intro_without=intro,
            list_text_getter=lambda: list_text,
        )

    def compact_openai_place_contexts(self, contexts: list[dict[str, str]]) -> list[dict[str, str]]:
        return _ppm_compact_openai_place_contexts(contexts)

    def show_admin_place_contexts_dialog(self) -> None:
        item = self.selected_admin_upload()
        if not item:
            return
        contexts = item.get("openai_place_contexts") or []
        if not isinstance(contexts, list) or not contexts:
            messagebox.showinfo("Fundstellen", "Für dieses Dokument sind keine gespeicherten Ortsanalyse-Fundstellen vorhanden.")
            return
        updated_at = str(item.get("openai_place_contexts_updated_at") or "").strip() or "-"
        model_name = str(item.get("openai_place_contexts_model") or "").strip() or "-"
        grouped: dict[str, list[str]] = {}
        for context in contexts:
            if not isinstance(context, dict):
                continue
            place = str(context.get("place") or "Ohne Ort").strip() or "Ohne Ort"
            text = str(context.get("text") or "").strip()
            if text:
                grouped.setdefault(place, []).append(text)
        dialog = tk.Toplevel(self)
        dialog.title("Gespeicherte Ortsanalyse-Fundstellen")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("900x650")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(
            dialog,
            text=f"Gespeicherte Fundstellen: {sum(len(values) for values in grouped.values())} | Modell: {model_name} | Aktualisiert: {updated_at}",
            wraplength=860,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        text = tk.Text(dialog, wrap="word")
        text.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=4)
        text.configure(yscrollcommand=scrollbar.set)
        for place, snippets in sorted(grouped.items(), key=lambda item: item[0].casefold()):
            text.insert("end", f"{place}\n", ("heading",))
            for idx, snippet in enumerate(snippets, start=1):
                text.insert("end", f"{idx}. {snippet}\n\n")
        text.tag_configure("heading", font=("", 10, "bold"))
        text.configure(state="disabled")
        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        self.wait_window(dialog)

    def show_admin_place_scan_result_dialog(
        self,
        item: dict,
        result: dict,
        contexts: list[dict[str, str]],
        usage_text: str,
        used_fallback: bool = False,
        model_name: str = "",
    ) -> None:
        summary = str(result.get("summary") or "").strip()
        keywords = str(result.get("keywords") or "").strip()
        places = str(result.get("places") or "").strip() or ", ".join(dict.fromkeys(context.get("place", "") for context in contexts if context.get("place")))
        document_date = str(result.get("document_date") or "").strip()
        event = str(result.get("event") or "").strip()
        primary_source = str(result.get("primary_source") or "").strip()
        description_suggestion = f"enthält u.a. {summary}" if summary and not summary.lower().startswith("enthält u.a.") else summary
        dialog = tk.Toplevel(self)
        dialog.title("OpenAI-Ortsanalyse")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("1180x720")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        mode_text = "Keine Ortsfundstelle lokal gefunden - begrenzte Textprobe nach OpenAI-Vorgaben geprüft" if used_fallback else f"Fundstellen: {len(contexts)}"
        model_text = str(model_name or "").strip() or "-"
        ttk.Label(dialog, text=f"Gefundene Orte: {places or '-'} | Modell: {model_text} | {mode_text} | {usage_text}\nJe Feld Aktion wählen; keine Auswahl bedeutet ignorieren.", wraplength=920).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        body = ttk.Frame(dialog)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        ttk.Label(body, text="Feldübernahme:").grid(row=0, column=0, sticky="w")
        rows = [
            ("document_date", "Datum / Zeitraum", self.current_admin_openai_field_value("document_date"), document_date),
            ("event", "Ereignis", self.current_admin_openai_field_value("event"), event),
            ("primary_source", "Primärquelle", self.current_admin_openai_field_value("primary_source"), primary_source),
            ("description", "Beschreibung", self.current_admin_openai_field_value("description"), description_suggestion),
            ("keywords", "Stichwörter", self.current_admin_openai_field_value("keywords"), keywords),
            ("place", "Ort", self.current_admin_openai_field_value("place"), places),
        ]
        rows = [(key, label, current, suggestion) for key, label, current, suggestion in rows if str(suggestion or "").strip()]
        transfer = ttk.Frame(body)
        transfer.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        headers = ["Feld", "Aktueller Wert", "OpenAI-Vorschlag", "übernehmen", "überschreiben", "anhängen"]
        widths = [16, 28, 42, 12, 14, 10]
        for col, (header, width) in enumerate(zip(headers, widths)):
            ttk.Label(transfer, text=header, font=("", 9, "bold"), width=width).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
        action_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        for row_idx, (key, label, current, suggestion) in enumerate(rows, start=1):
            row_vars = {
                "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
                "replace": tk.BooleanVar(value=False),
                "append": tk.BooleanVar(value=False),
            }
            action_vars[key] = row_vars
            row_height = max(self._openai_display_height(current, wrap_at=58, max_lines=12), self._openai_display_height(suggestion, wrap_at=58, max_lines=12))
            ttk.Label(transfer, text=label, width=16).grid(row=row_idx, column=0, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(transfer, current or "-", width=30, height=row_height, background_source=dialog).grid(row=row_idx, column=1, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(transfer, suggestion, width=62, height=row_height, background_source=dialog).grid(row=row_idx, column=2, sticky="nw", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["take"], command=lambda vars=row_vars: self._choose_openai_action(vars, "take")).grid(row=row_idx, column=3, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["replace"], command=lambda vars=row_vars: self._choose_openai_action(vars, "replace")).grid(row=row_idx, column=4, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["append"], command=lambda vars=row_vars: self._choose_openai_action(vars, "append")).grid(row=row_idx, column=5, sticky="n", padx=4, pady=3)

        ttk.Label(body, text="Verwendete lokale Fundstellen:").grid(row=2, column=0, sticky="w")
        contexts_text = tk.Text(body, height=9, wrap="word")
        contexts_text.grid(row=3, column=0, sticky="nsew", pady=(2, 0))
        if contexts:
            for idx, context in enumerate(contexts, start=1):
                contexts_text.insert("end", f"{idx}. {context.get('place', '')}\n{context.get('text', '')}\n\n")
        else:
            contexts_text.insert("end", "Keine lokale Ortsfundstelle. OpenAI hat die begrenzte Textprobe nach den OpenAI-Einstellungen ausgewertet.")
        contexts_text.configure(state="disabled")

        def apply_to_metadata() -> None:
            analysis_model = str(model_name or self.config_data.get("openai_model", "") or "").strip()
            analysis_time = datetime.now().isoformat(timespec="seconds")
            changed = []
            for key, _label, current, suggestion in rows:
                selected = [action_name for action_name, var in action_vars[key].items() if var.get()]
                action = selected[0] if selected else ""
                if not action:
                    continue
                new_value = self.admin_openai_value_for_action(key, current, suggestion, action)
                if new_value != current:
                    self.set_admin_openai_field_value(key, new_value)
                    changed.append(key)
            if changed:
                previous_fields = [str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()]
                item["openai_metadata_fields"] = list(dict.fromkeys(previous_fields + changed))
                item["openai_metadata_model"] = analysis_model
                item["openai_metadata_applied_at"] = datetime.now().isoformat(timespec="seconds")
                item["openai_place_contexts_model"] = analysis_model
                item["openai_place_contexts_updated_at"] = analysis_time
                if contexts:
                    item["openai_place_contexts"] = self.compact_openai_place_contexts(contexts)
                append_metadata_history(item, self.display_name_var.get().strip() or "Admin", "OpenAI-Ortsanalyse übernommen", f"Felder: {', '.join(changed)}; Orte: {places}")
                self.persist_admin_openai_form_item(item)
                api_ok, api_msg = self.save_admin_openai_item_to_storage(item)
                if api_ok:
                    self.update_admin_tree_row_for_item(item)
                    self.update_admin_openai_controls()
                    self.admin_openai_status_var.set(f"Ortsanalyse übernommen und gespeichert: {', '.join(changed)}")
                else:
                    self.update_admin_openai_controls()
                    self.admin_openai_status_var.set(f"Ortsanalyse lokal übernommen; MySQL nicht gespeichert: {api_msg}")
            else:
                item["openai_place_contexts_model"] = analysis_model
                item["openai_place_contexts_updated_at"] = analysis_time
                if contexts:
                    item["openai_place_contexts"] = self.compact_openai_place_contexts(contexts)
                api_ok, api_msg = self.save_admin_openai_item_to_storage(item)
                if api_ok:
                    self.update_admin_tree_row_for_item(item)
                    self.update_admin_openai_controls()
                    self.admin_openai_status_var.set("Ortsanalyse gespeichert: keine Felder übernommen")
                else:
                    self.update_admin_openai_controls()
                    self.admin_openai_status_var.set(f"Ortsanalyse lokal gespeichert; MySQL nicht aktualisiert: {api_msg}")
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, sticky="e", padx=12, pady=(8, 12))
        ttk.Button(buttons, text="Auswahl übernehmen", command=apply_to_metadata).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
        self.wait_window(dialog)

    def choose_admin_openai_model(self, item: dict) -> str:
        used_models = self.openai_used_models(item, "openai_model_results", "openai_metadata_model")
        previous_fields = ", ".join(str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()) or "-"
        previous_time = str(item.get("openai_metadata_applied_at") or "").strip() or "-"
        return self._resolve_openai_model_dialog_result(
            item=item,
            result_field="openai_model_results",
            legacy_model_field="openai_metadata_model",
            previous_time_field="openai_metadata_applied_at",
            used_fallback=False,
            accept_label="OpenAI prüfen",
            title_with_fallback="OpenAI-Modell wählen",
            title_without="OpenAI-Modell wählen",
            intro_with_fallback=f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}\n\nBisherige Felder: {previous_fields}\n\nZeitpunkt: {previous_time}",
            intro_without=f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}\n\nBisherige Felder: {previous_fields}\n\nZeitpunkt: {previous_time}",
            list_text_getter=lambda: "\n".join(
                [
                    f"Bisheriges OpenAI-Modell: {', '.join(used_models) or 'noch keine OpenAI-Prüfung'}",
                    f"Bisherige Felder: {previous_fields}",
                    f"Letzter Stand: {previous_time}",
                    "",
                    "Neu prüfen mit Modell:",
                ]
            ),
        )

    def show_admin_openai_apply_dialog(self, suggestions: dict) -> list[str] | None:
        excluded_fields = {"document_type"}
        rows = []
        active_vars = self.active_admin_openai_meta_vars()
        for key, value in suggestions.items():
            if key in excluded_fields:
                continue
            text = str(value or "").strip()
            if not text:
                continue
            current = self.current_admin_openai_field_value(key)
            if key == "description" or key in active_vars:
                rows.append((key, current, text))
        if not rows:
            messagebox.showinfo("OpenAI", "OpenAI hat keine übernehmbaren Metadatenvorschläge geliefert.")
            return []

        dialog = tk.Toplevel(self)
        dialog.title("OpenAI-Metadaten übernehmen")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("1180x680")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(
            dialog,
            text="Wählen Sie je Feld eine Aktion. Keine Auswahl bedeutet: Vorschlag ignorieren.",
            wraplength=920,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        canvas = tk.Canvas(dialog, highlightthickness=0)
        scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=4)
        scroll.grid(row=1, column=1, sticky="ns", pady=4)
        headers = ["Feld", "Aktueller Wert", "OpenAI-Vorschlag", "übernehmen", "überschreiben", "anfügen"]
        widths = [18, 30, 34, 12, 14, 10]
        for col, (header, width) in enumerate(zip(headers, widths)):
            ttk.Label(inner, text=header, font=("", 9, "bold"), width=width).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))
        action_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        for row_index, (key, current, suggestion) in enumerate(rows, start=1):
            row_vars = {
                "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
                "replace": tk.BooleanVar(value=False),
                "append": tk.BooleanVar(value=False),
            }
            action_vars[key] = row_vars
            row_height = max(self._openai_display_height(current), self._openai_display_height(suggestion))
            ttk.Label(inner, text=self.admin_openai_field_label(key), width=18).grid(row=row_index, column=0, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(inner, current or "-", width=34, height=row_height, background_source=dialog).grid(row=row_index, column=1, sticky="nw", padx=4, pady=3)
            self._readonly_text_widget(inner, suggestion, width=56, height=row_height, background_source=dialog).grid(row=row_index, column=2, sticky="nw", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["take"], command=lambda vars=row_vars: self._choose_openai_action(vars, "take")).grid(row=row_index, column=3, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["replace"], command=lambda vars=row_vars: self._choose_openai_action(vars, "replace")).grid(row=row_index, column=4, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["append"], command=lambda vars=row_vars: self._choose_openai_action(vars, "append")).grid(row=row_index, column=5, sticky="n", padx=4, pady=3)
        result = {"changed": None}

        def apply_selection() -> None:
            changed: list[str] = []
            for key, current, suggestion in rows:
                selected = [action_name for action_name, var in action_vars[key].items() if var.get()]
                action = selected[0] if selected else ""
                if not action:
                    continue
                new_value = self.admin_openai_value_for_action(key, current, suggestion, action)
                if new_value != current:
                    self.set_admin_openai_field_value(key, new_value)
                    changed.append(key)
            result["changed"] = changed
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 12))
        ttk.Button(buttons, text="Auswahl übernehmen", command=apply_selection).pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
        self.wait_window(dialog)
        return result["changed"]

    def current_admin_openai_field_value(self, key: str) -> str:
        if self.use_file_view_openai_form():
            if key == "description":
                return self.file_view_description_text.get("1.0", "end").strip()
            var = self.file_view_meta_vars.get(key)
            return str(var.get() or "").strip() if var is not None else ""
        if key == "description":
            return self.admin_description_text.get("1.0", "end").strip()
        var = self.admin_meta_vars.get(key)
        return str(var.get() or "").strip() if var is not None else ""

    def set_admin_openai_field_value(self, key: str, value: str) -> None:
        if self.use_file_view_openai_form():
            if key == "description":
                value = self.normalize_description_text(value)
                self.file_view_description_text.delete("1.0", "end")
                self.file_view_description_text.insert("1.0", value)
                return
            var = self.file_view_meta_vars.get(key)
            if var is not None:
                var.set(value)
            return
        if key == "description":
            value = self.normalize_description_text(value)
            self.admin_description_text.delete("1.0", "end")
            self.admin_description_text.insert("1.0", value)
            return
        var = self.admin_meta_vars.get(key)
        if var is not None:
            var.set(value)

    def use_file_view_openai_form(self) -> bool:
        return bool(self.is_unified_file_view_active())

    def active_admin_openai_meta_vars(self) -> dict:
        if self.use_file_view_openai_form():
            return self.file_view_meta_vars
        return self.admin_meta_vars

    def persist_admin_openai_form_item(self, item: dict) -> None:
        """Persist the visible admin metadata form into the concrete analyzed item."""
        technical_edit_keys = {"upload_id", "edited_by", "edited_at"}
        meta_vars = self.active_admin_openai_meta_vars()
        for key, var in meta_vars.items():
            if key in technical_edit_keys:
                continue
            raw_value = var.get()
            item[key] = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
        description_widget = self.file_view_description_text if self.use_file_view_openai_form() else self.admin_description_text
        note_widget = self.file_view_note_text if self.use_file_view_openai_form() else self.admin_note_text
        if description_widget is not None:
            item["description"] = self.normalize_description_text(description_widget.get("1.0", "end").strip())
        if note_widget is not None:
            item["note"] = note_widget.get("1.0", "end").strip()
        display_name = self.display_name_var.get().strip() or "Admin"
        edited_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item["edited_by"] = display_name
        item["edited_at"] = edited_at
        if "edited_by" in meta_vars:
            meta_vars["edited_by"].set(display_name)
        if "edited_at" in meta_vars:
            meta_vars["edited_at"].set(edited_at)

    def save_admin_openai_item_to_storage(self, item: dict) -> tuple[bool, str]:
        if bool(item.get("_missing_odv_entry")):
            path_text = str(item.get("current_path") or "").strip()
            path = Path(path_text) if path_text else None
            if path is None or not path.exists() or not path.is_file():
                return False, "Lokale Datei für neuen ODV-Eintrag nicht gefunden"
            tree_iid = str(item.get("_tree_iid") or item.get("upload_id") or "")
            new_item, metadata_file = self.ensure_file_view_metadata_item(path)
            real_upload_id = str(new_item.get("upload_id") or "")
            metadata_file_text = str(metadata_file)
            pending_flag = bool(new_item.get("_pending_existing_file_metadata", True))
            for key, value in list(item.items()):
                if key in {"upload_id", "_display_upload_id", "_display_status", "_display_by", "_display_date", "_tree_iid"}:
                    continue
                if key.startswith("_") and key not in {"_metadata_file"}:
                    continue
                new_item[key] = value
            new_item["upload_id"] = real_upload_id
            new_item["_metadata_file"] = metadata_file_text
            new_item["_pending_existing_file_metadata"] = pending_flag
            new_item["_tree_iid"] = tree_iid
            new_item["_display_upload_id"] = real_upload_id
            new_item["_display_status"] = new_item.get("status") or "erfasst"
            new_item["status"] = "erfasst" if str(new_item.get("status") or "").strip() == "ohne" else str(new_item.get("status") or "erfasst")
            display_name = self.display_name_var.get().strip() or "Admin"
            append_metadata_history(new_item, display_name, "Vorhandene Datei durch OpenAI-Ortsanalyse in ODV aufgenommen", path.name)
            ok, msg = self.save_file_view_item_to_storage(new_item, metadata_file, True)
            item.clear()
            item.update(new_item)
            item.pop("_missing_odv_entry", None)
            item.pop("_pending_existing_file_metadata", None)
            return ok, msg
        api_ok, api_msg = self.save_item_to_api(item)
        self.save_item_json_if_present(item)
        return api_ok, api_msg

    def update_admin_tree_row_for_item(self, item: dict) -> None:
        if self.is_unified_file_view_active():
            self.file_view_current_metadata = item
            self.load_file_view_metadata_form()
            try:
                self.refresh_file_view_tree()
            except Exception:
                pass
            return
        tree_iid = str(item.get("_tree_iid") or item.get("upload_id") or "")
        if not tree_iid or not self.admin_tree.exists(tree_iid):
            return
        self.admin_tree.item(
            tree_iid,
            values=(
                item.get("_display_upload_id") or item.get("upload_id") or "",
                item.get("_display_status") or item.get("status", "hochgeladen"),
                item.get("current_filename") or item.get("stored_filename") or item.get("original_filename", ""),
                item.get("_display_by") if "_display_by" in item else (item.get("uploaded_by") or item.get("uploaded_by_name", "")),
                item.get("_display_date") if "_display_date" in item else item.get("uploaded_at", ""),
                item.get("document_type", ""),
            ),
        )

    def admin_openai_value_for_action(self, key: str, current: str, suggestion: str, action: str) -> str:
        current = str(current or "").strip()
        suggestion = str(suggestion or "").strip()
        if action == "take":
            if not current:
                return suggestion
            if key == "place":
                return self.merge_place_values(current, suggestion)
            if key == "keywords":
                return self.merge_metadata_values(current, suggestion, separator=", ")
            return suggestion
        if action == "replace":
            return suggestion
        if action == "append":
            if key == "description":
                return self.append_openai_description(current, suggestion)
            if key == "place":
                return self.merge_place_values(current, suggestion)
            return self.merge_metadata_values(current, suggestion, separator=", " if key == "keywords" else "; ")
        return current

    def admin_openai_field_label(self, key: str) -> str:
        labels = {
            "document_type": "Dokumenttyp",
            "document_date": "Datum / Zeitraum",
            "place": "Ort",
            "event": "Ereignis",
            "keywords": "Stichwörter",
            "description": "Beschreibung",
            "primary_source": "Primärquelle",
            "secondary_source": "Sekundärquelle",
            "original_location": "Standort Original",
            "archive_name": "Archiv",
            "archive_signature": "Signatur",
            "archive_accessed_at": "Abruf am",
            "copyright_author": "Urheber/in",
            "rights_holder": "Rechteinhaber",
            "usage_permission": "Nutzungsfreigabe",
            "license_note": "Lizenz",
            "rights_note": "Rechte",
        }
        return labels.get(key, key)
