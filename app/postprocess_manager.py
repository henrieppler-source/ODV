from __future__ import annotations

from pathlib import Path
from datetime import datetime
import threading
import re
import tkinter as tk
from tkinter import ttk, messagebox

from .app_logging import app_log_exception
from .file_service import append_metadata_history, unique_path_with_counter
from .openai_client import OpenAIClient, OpenAIError


class PostprocessManagerMixin:
    """OpenAI-, OCR- und Nachbearbeitungshelfer für die zentrale Dateiliste."""

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
        if hasattr(self, "is_unified_file_view_active") and self.is_unified_file_view_active():
            path = getattr(self, "file_view_current_path", None)
            if path is not None and path.exists() and path.is_file():
                return path
        item = self.selected_admin_upload() if hasattr(self, "selected_admin_upload") else None
        if not item:
            return None
        return self.resolve_document_local_path(item)

    def update_admin_openai_controls(self) -> None:
        if not hasattr(self, "admin_openai_button"):
            return
        path = self.admin_selected_document_path()
        for button_name in ("admin_openai_button", "admin_openai_places_button", "admin_place_contexts_button", "admin_ocr_pdf_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.grid_remove()
        if path is None or not path.exists() or not path.is_file():
            self.admin_openai_status_var.set("OpenAI: keine Datei ausgewählt")
            return
        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".txt", ".md", ".csv", ".log", ".docx", ".odt"}:
            self.admin_openai_status_var.set("OpenAI: Datei ist kein lesbares Textdokument/PDF")
            return
        analysis_path = self.existing_ocr_pdf_for_path(path) or path
        sample = self.extract_upload_text_sample(analysis_path, max_chars=500, max_pdf_pages=2)
        item = self.selected_admin_upload() or {}
        if hasattr(self, "is_unified_file_view_active") and self.is_unified_file_view_active():
            can_edit = self.can_edit_file_view_metadata(path, item)
        else:
            can_edit = self.can_edit_admin_item(item)
        contexts_button = getattr(self, "admin_place_contexts_button", None)
        contexts_available = bool(item.get("openai_place_contexts"))
        if contexts_button is not None and contexts_available:
            contexts_button.grid()
            contexts_button.configure(state="normal")
        if sample:
            self.admin_openai_button.grid()
            self.admin_openai_button.configure(state=("normal" if can_edit else "disabled"))
            if hasattr(self, "admin_openai_places_button"):
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
                    if hasattr(self, "is_unified_file_view_active") and self.is_unified_file_view_active():
                        self.file_view_current_metadata = item
                        if hasattr(self, "load_file_view_metadata_form"):
                            self.load_file_view_metadata_form()
                    elif getattr(self, "legacy_admin_table_is_active", lambda: False)():
                        self.show_selected_admin_details()
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
        api_key = str(getattr(self, "config_data", {}).get("openai_api_key", "") or "").strip()
        if not api_key:
            messagebox.showwarning("OpenAI", "OpenAI ist nicht konfiguriert.")
            return
        client = OpenAIClient(api_key=api_key, model=selected_model)
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
        results = item.get(field)
        if not isinstance(results, dict):
            return {}
        wanted = str(model or "").casefold()
        for stored_model, data in results.items():
            if str(stored_model or "").casefold() == wanted and isinstance(data, dict):
                return data
        return {}

    def store_openai_model_result(self, item: dict, model: str, field: str, data: dict) -> None:
        model = str(model or "").strip()
        if not model:
            return
        results = item.get(field)
        if not isinstance(results, dict):
            results = {}
        results[model] = data
        item[field] = results

    def openai_used_models(self, item: dict, field: str, legacy_model_field: str = "") -> list[str]:
        models: list[str] = []
        results = item.get(field)
        if isinstance(results, dict):
            models.extend(str(model).strip() for model in results.keys() if str(model).strip())
        if legacy_model_field:
            legacy = str(item.get(legacy_model_field) or "").strip()
            if legacy:
                models.append(legacy)
        return list(dict.fromkeys(models))

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
        names: set[str] = set()
        for value in getattr(self, "place_folder_map", {}).keys():
            text = str(value or "").strip()
            if text:
                names.add(text)
        for value in getattr(self, "place_folder_map", {}).values():
            folder = Path(str(value or ""))
            name = folder.name.strip()
            if "_" in name:
                name = name.split("_", 1)[1]
            if name:
                names.add(name.replace("_", " "))
        try:
            current = self.place_var.get().strip()
            if current:
                names.add(current)
        except Exception:
            pass
        return sorted((name for name in names if len(name) >= 3), key=lambda name: (-len(name), name.casefold()))

    def find_place_contexts_in_text(self, text: str, places: list[str], context_chars: int = 650, max_contexts: int = 30) -> list[dict[str, str]]:
        contexts: list[dict[str, str]] = []
        seen: set[tuple[str, int]] = set()
        normalized_text = str(text or "")
        for place in places:
            variants = {place}
            variants.add(place.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue").replace("ß", "ss"))
            variants.add(place.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("Ä", "A").replace("Ö", "O").replace("Ü", "U").replace("ß", "ss"))
            variant_pattern = "|".join(re.escape(variant) for variant in sorted(variants, key=len, reverse=True) if variant)
            if not variant_pattern:
                continue
            pattern = re.compile(rf"(?<!\w)(?:{variant_pattern})(?!\w)", flags=re.IGNORECASE)
            for match in pattern.finditer(normalized_text):
                start = max(0, match.start() - context_chars)
                end = min(len(normalized_text), match.end() + context_chars)
                key = (place.casefold(), start)
                if key in seen:
                    continue
                seen.add(key)
                snippet = self.clean_place_context_text(normalized_text[start:end])
                if snippet:
                    contexts.append({"place": place, "text": snippet})
                if len(contexts) >= max_contexts:
                    return contexts
        return contexts

    def clean_place_context_text(self, text: str) -> str:
        """Glättet PDF-/OCR-Textausschnitte für Ortsanalyse und Anzeige."""
        value = str(text or "")
        if not value.strip():
            return ""
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        # Klassische Silbentrennung am Zeilenende: "Septem-\nber" -> "September".
        value = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])-+\s*\n\s*(?=[A-Za-zÄÖÜäöüß])", "", value)
        # PDF-Extraktion liefert Zeilen oft hart getrennt; für Fundstellen lieber Fließtext.
        value = re.sub(r"\s*\n\s*", " ", value)
        # Silbentrennung, die bereits zu Leerraum normalisiert wurde: "Septem- ber" -> "September".
        value = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])-+\s+(?=[a-zäöüß])", "", value)
        # Fehlendes Leerzeichen zwischen Klein- und Großbuchstaben: "ausRömhild" -> "aus Römhild".
        value = re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", value)
        # OCR trennt Anfangsbuchstaben gelegentlich ab: "R ömhild" -> "Römhild".
        value = re.sub(r"\b([A-ZÄÖÜ])\s+([a-zäöüß]{2,})\b", r"\1\2", value)
        # Häufige OCR-Brüche bei kurzen deutschen Funktionswörtern.
        common_tail_words = {
            "d": {"em", "er", "ie", "as", "en"},
            "n": {"icht"},
            "a": {"us"},
            "s": {"ich"},
            "m": {"it"},
            "u": {"nd"},
        }
        for first_letter, tails in common_tail_words.items():
            tail_pattern = "|".join(sorted(tails, key=len, reverse=True))
            value = re.sub(
                rf"\b([A-Za-zÄÖÜäöüß]{{3,}})({first_letter})\s+({tail_pattern})\b",
                lambda match: f"{match.group(1)} {match.group(2)}{match.group(3)}",
                value,
                flags=re.IGNORECASE,
            )
        # Häufige Restartefakte nach PDF-Spalten-/Zeilenumbruch.
        value = value.replace("„ ", "„").replace(" “", "“").replace(" ,", ",").replace(" .", ".")
        value = re.sub(r"[ \t]{2,}", " ", value)
        return value.strip()

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
        try:
            place_context_chars = max(100, min(6000, int(getattr(self, "config_data", {}).get("openai_place_context_chars", 650) or 650)))
        except Exception:
            place_context_chars = 650
        try:
            place_max_contexts = max(1, min(200, int(getattr(self, "config_data", {}).get("openai_place_max_contexts", 30) or 30)))
        except Exception:
            place_max_contexts = 30
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
        api_key = str(getattr(self, "config_data", {}).get("openai_api_key", "") or "").strip()
        if not api_key:
            messagebox.showwarning("OpenAI", "OpenAI ist nicht konfiguriert.")
            return
        client = OpenAIClient(api_key=api_key, model=selected_model)
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
        counts: dict[str, int] = {}
        for context in contexts:
            place = str(context.get("place") or "").strip()
            if place:
                counts[place] = counts.get(place, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[0].casefold()))

    def confirm_admin_place_scan_openai(self, item: dict, contexts: list[dict[str, str]], used_fallback: bool = False) -> str:
        dialog = tk.Toplevel(self)
        dialog.title("Orte lokal gefunden" if not used_fallback else "Keine Orte lokal gefunden")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("560x470")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)
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
        current_model = str(getattr(self, "config_data", {}).get("openai_model", "gpt-4o-mini") or "gpt-4o-mini").strip()
        used_models = self.openai_used_models(item, "openai_place_model_results", "openai_place_contexts_model")
        previous_model = ", ".join(used_models)
        previous_time = str(item.get("openai_place_contexts_updated_at") or "").strip() or "-"
        model_values = []
        for model in [current_model, "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]:
            if model and model not in model_values:
                model_values.append(model)
        for model in used_models:
            if model and model not in model_values:
                model_values.append(model)
        ttk.Label(dialog, text=intro, wraplength=520).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        model_frame = ttk.Frame(dialog)
        model_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        model_frame.columnconfigure(1, weight=1)
        ttk.Label(model_frame, text="OpenAI-Modell:").grid(row=0, column=0, sticky="w")
        model_var = tk.StringVar(value=current_model)
        model_combo = ttk.Combobox(model_frame, textvariable=model_var, values=model_values, state="readonly", width=28)
        model_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        info_var = tk.StringVar(value="")
        ttk.Label(model_frame, textvariable=info_var, foreground="#555555", wraplength=520).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
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
            cached = bool(self.openai_cached_model_result(item, selected, "openai_place_model_results"))
            if cached:
                info_var.set(f"Dieses Dokument wurde für Orte prüfen bereits mit diesem Modell verarbeitet ({previous_time}). Gespeicherte Vorschläge werden angezeigt.")
                continue_button.configure(text="Gespeicherte Vorschläge anzeigen", state="normal")
            else:
                info_var.set("OpenAI startet erst nach Bestätigung und verursacht Kosten.")
                continue_button.configure(text="Mit OpenAI fortfahren", state="normal")

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, sticky="e", padx=12, pady=(8, 12))
        continue_button = ttk.Button(buttons, text="Mit OpenAI fortfahren", command=accept)
        continue_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
        model_var.trace_add("write", refresh_info)
        refresh_info()
        self.wait_window(dialog)
        return result["model"]

    def compact_openai_place_contexts(self, contexts: list[dict[str, str]]) -> list[dict[str, str]]:
        compact: list[dict[str, str]] = []
        for context in contexts:
            place = str(context.get("place") or "").strip()
            text = self.clean_place_context_text(str(context.get("text") or ""))
            if not place or not text:
                continue
            compact.append({"place": place, "text": text[:1500]})
        return compact

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

        def choose_action(row_vars: dict[str, tk.BooleanVar], selected_action: str) -> None:
            if not row_vars[selected_action].get():
                return
            for action_name, var in row_vars.items():
                if action_name != selected_action:
                    var.set(False)

        def readonly_text(parent: tk.Widget, value: str, width: int, height: int) -> tk.Text:
            text_widget = tk.Text(
                parent,
                width=width,
                height=height,
                wrap="word",
                relief="flat",
                borderwidth=0,
                background=dialog.cget("background"),
                font=("TkDefaultFont", 9),
            )
            text_widget.insert("1.0", value or "-")
            text_widget.configure(state="disabled")
            return text_widget

        def display_height(value: str, wrap_at: int = 58) -> int:
            text = str(value or "")
            line_count = max(1, len(text.splitlines()))
            estimated_wrap_lines = max(1, (len(text) + max(1, wrap_at - 1)) // max(1, wrap_at))
            return min(12, max(line_count, estimated_wrap_lines))

        for row_idx, (key, label, current, suggestion) in enumerate(rows, start=1):
            row_vars = {
                "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
                "replace": tk.BooleanVar(value=False),
                "append": tk.BooleanVar(value=False),
            }
            action_vars[key] = row_vars
            row_height = max(display_height(current), display_height(suggestion))
            ttk.Label(transfer, text=label, width=16).grid(row=row_idx, column=0, sticky="nw", padx=4, pady=3)
            readonly_text(transfer, current or "-", width=30, height=row_height).grid(row=row_idx, column=1, sticky="nw", padx=4, pady=3)
            readonly_text(transfer, suggestion, width=62, height=row_height).grid(row=row_idx, column=2, sticky="nw", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["take"], command=lambda vars=row_vars: choose_action(vars, "take")).grid(row=row_idx, column=3, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["replace"], command=lambda vars=row_vars: choose_action(vars, "replace")).grid(row=row_idx, column=4, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(transfer, variable=row_vars["append"], command=lambda vars=row_vars: choose_action(vars, "append")).grid(row=row_idx, column=5, sticky="n", padx=4, pady=3)

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
            analysis_model = str(model_name or getattr(self, "config_data", {}).get("openai_model", "") or "").strip()
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
        current_model = str(getattr(self, "config_data", {}).get("openai_model", "gpt-4o-mini") or "gpt-4o-mini").strip()
        used_models = self.openai_used_models(item, "openai_model_results", "openai_metadata_model")
        previous_model = ", ".join(used_models)
        previous_fields = ", ".join(str(field) for field in (item.get("openai_metadata_fields", []) or []) if str(field).strip()) or "-"
        previous_time = str(item.get("openai_metadata_applied_at") or "").strip() or "-"
        model_values = []
        for model in [current_model, "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]:
            if model and model not in model_values:
                model_values.append(model)
        for model in used_models:
            if model and model not in model_values:
                model_values.append(model)

        dialog = tk.Toplevel(self)
        dialog.title("OpenAI-Modell wählen")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        ttk.Label(dialog, text="Bisheriges OpenAI-Modell:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ttk.Label(dialog, text=previous_model or "noch keine OpenAI-Prüfung").grid(row=0, column=1, sticky="w", padx=12, pady=(12, 4))
        ttk.Label(dialog, text="Bisherige Felder:").grid(row=1, column=0, sticky="nw", padx=12, pady=4)
        ttk.Label(dialog, text=previous_fields, wraplength=420).grid(row=1, column=1, sticky="w", padx=12, pady=4)
        ttk.Label(dialog, text="Zeitpunkt:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        ttk.Label(dialog, text=previous_time).grid(row=2, column=1, sticky="w", padx=12, pady=4)
        ttk.Label(dialog, text="Neu prüfen mit Modell:").grid(row=3, column=0, sticky="w", padx=12, pady=(10, 4))
        model_var = tk.StringVar(value=current_model)
        combo = ttk.Combobox(dialog, textvariable=model_var, values=model_values, state="readonly", width=34)
        combo.grid(row=3, column=1, sticky="ew", padx=12, pady=(10, 4))
        info_var = tk.StringVar()
        result = {"model": ""}

        def refresh_info(*_args) -> None:
            selected = model_var.get().strip()
            cached = bool(self.openai_cached_model_result(item, selected, "openai_model_results"))
            if cached:
                info_var.set("Dieses Modell wurde bereits verwendet. Es werden die gespeicherten Vorschläge angezeigt, kein neuer API-Aufruf.")
                ok_button.configure(text="Gespeicherte Vorschläge anzeigen", state="normal")
            else:
                info_var.set("Der OpenAI-Aufruf verursacht Kosten. Bitte Modell bewusst wählen.")
                ok_button.configure(text="OpenAI prüfen", state="normal")

        def accept() -> None:
            result["model"] = model_var.get().strip()
            dialog.destroy()

        ttk.Label(dialog, textvariable=info_var, foreground="#555555", wraplength=540).grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 10))
        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 12))
        ok_button = ttk.Button(buttons, text="OpenAI prüfen", command=accept)
        ok_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
        model_var.trace_add("write", refresh_info)
        refresh_info()
        combo.focus_set()
        self.wait_window(dialog)
        return result["model"]

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

        def choose_action(row_vars: dict[str, tk.BooleanVar], selected_action: str) -> None:
            if not row_vars[selected_action].get():
                return
            for action_name, var in row_vars.items():
                if action_name != selected_action:
                    var.set(False)

        def readonly_text(parent: tk.Widget, value: str, width: int, height: int) -> tk.Text:
            text_widget = tk.Text(
                parent,
                width=width,
                height=height,
                wrap="word",
                relief="flat",
                borderwidth=0,
                background=dialog.cget("background"),
                font=("TkDefaultFont", 9),
            )
            text_widget.insert("1.0", value or "-")
            text_widget.configure(state="disabled")
            return text_widget

        def display_height(value: str) -> int:
            line_count = max(1, len(str(value or "").splitlines()))
            estimated_wrap_lines = max(1, (len(str(value or "")) + 54) // 55)
            return min(10, max(line_count, estimated_wrap_lines))

        for row_index, (key, current, suggestion) in enumerate(rows, start=1):
            row_vars = {
                "take": tk.BooleanVar(value=not bool(str(current or "").strip())),
                "replace": tk.BooleanVar(value=False),
                "append": tk.BooleanVar(value=False),
            }
            action_vars[key] = row_vars
            row_height = max(display_height(current), display_height(suggestion))
            ttk.Label(inner, text=self.admin_openai_field_label(key), width=18).grid(row=row_index, column=0, sticky="nw", padx=4, pady=3)
            readonly_text(inner, current or "-", width=34, height=row_height).grid(row=row_index, column=1, sticky="nw", padx=4, pady=3)
            readonly_text(inner, suggestion, width=56, height=row_height).grid(row=row_index, column=2, sticky="nw", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["take"], command=lambda vars=row_vars: choose_action(vars, "take")).grid(row=row_index, column=3, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["replace"], command=lambda vars=row_vars: choose_action(vars, "replace")).grid(row=row_index, column=4, sticky="n", padx=4, pady=3)
            ttk.Checkbutton(inner, variable=row_vars["append"], command=lambda vars=row_vars: choose_action(vars, "append")).grid(row=row_index, column=5, sticky="n", padx=4, pady=3)
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
            if key == "description" and hasattr(self, "file_view_description_text"):
                return self.file_view_description_text.get("1.0", "end").strip()
            var = getattr(self, "file_view_meta_vars", {}).get(key)
            return str(var.get() or "").strip() if var is not None else ""
        if key == "description" and hasattr(self, "admin_description_text"):
            return self.admin_description_text.get("1.0", "end").strip()
        var = getattr(self, "admin_meta_vars", {}).get(key)
        return str(var.get() or "").strip() if var is not None else ""

    def set_admin_openai_field_value(self, key: str, value: str) -> None:
        if self.use_file_view_openai_form():
            if key == "description" and hasattr(self, "file_view_description_text"):
                value = self.normalize_description_text(value)
                self.file_view_description_text.delete("1.0", "end")
                self.file_view_description_text.insert("1.0", value)
                return
            var = getattr(self, "file_view_meta_vars", {}).get(key)
            if var is not None:
                var.set(value)
            return
        if key == "description" and hasattr(self, "admin_description_text"):
            value = self.normalize_description_text(value)
            self.admin_description_text.delete("1.0", "end")
            self.admin_description_text.insert("1.0", value)
            return
        var = getattr(self, "admin_meta_vars", {}).get(key)
        if var is not None:
            var.set(value)

    def use_file_view_openai_form(self) -> bool:
        return bool(
            hasattr(self, "is_unified_file_view_active")
            and self.is_unified_file_view_active()
            and hasattr(self, "file_view_meta_vars")
        )

    def active_admin_openai_meta_vars(self) -> dict:
        if self.use_file_view_openai_form():
            return getattr(self, "file_view_meta_vars", {})
        return getattr(self, "admin_meta_vars", {})

    def persist_admin_openai_form_item(self, item: dict) -> None:
        """Persist the visible admin metadata form into the concrete analyzed item."""
        technical_edit_keys = {"upload_id", "edited_by", "edited_at"}
        meta_vars = self.active_admin_openai_meta_vars()
        for key, var in meta_vars.items():
            if key in technical_edit_keys:
                continue
            raw_value = var.get()
            item[key] = "1" if isinstance(var, tk.BooleanVar) and bool(raw_value) else ("0" if isinstance(var, tk.BooleanVar) else str(raw_value).strip())
        description_widget = getattr(self, "file_view_description_text", None) if self.use_file_view_openai_form() else getattr(self, "admin_description_text", None)
        note_widget = getattr(self, "file_view_note_text", None) if self.use_file_view_openai_form() else getattr(self, "admin_note_text", None)
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
        if hasattr(self, "is_unified_file_view_active") and self.is_unified_file_view_active():
            self.file_view_current_metadata = item
            if hasattr(self, "load_file_view_metadata_form"):
                self.load_file_view_metadata_form()
            if hasattr(self, "refresh_file_view_tree"):
                try:
                    self.refresh_file_view_tree()
                except Exception:
                    pass
            return
        tree_iid = str(item.get("_tree_iid") or item.get("upload_id") or "")
        if not tree_iid or not hasattr(self, "admin_tree") or not self.admin_tree.exists(tree_iid):
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
