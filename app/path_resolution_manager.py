from __future__ import annotations

import os
from pathlib import Path


class PathResolutionManagerMixin:
    def normalize_local_path_text(self, value: str | Path) -> str:
        """Lokale Pfade einheitlich im Betriebssystemformat darstellen."""
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return os.path.normpath(text)
        except Exception:
            return text.replace("/", "\\") if os.name == "nt" else text.replace("\\", "/")

    def known_top_folder_tokens(self) -> set[str]:
        tokens = {self.normalize_folder_token(key) for key, _label in self.FOLDER_GROUPS if not key.endswith("_FOLDER")}
        tokens.update({self.normalize_folder_token(v) for v in self.place_folder_map.values() if v})
        tokens.update({self.normalize_folder_token(v) for v in self.admin_work_folder_names if v})
        return {t for t in tokens if t}

    def document_candidate_suffixes(self, item: dict | None) -> list[str]:
        """Mögliche Dateiendungen aus DB-Feldern und Dokumenttyp ableiten.

        Ältere Datensätze enthalten teilweise Dateinamen ohne echte Endung oder mit
        ersetztem Punkt, z. B. ``datei_jpg`` statt ``datei.jpg``. Diese Liste hilft
        der Dateiauflösung, solche Fälle trotzdem im Nextcloud-Ordner zu finden.
        """
        suffixes: list[str] = []
        if item:
            for key in ("current_filename", "stored_filename", "original_filename", "current_path", "target_folder"):
                value = str(item.get(key) or "").strip()
                if not value:
                    continue
                suffix = Path(value).suffix.lower()
                if suffix and suffix not in suffixes:
                    suffixes.append(suffix)
            doc_type = str(item.get("document_type") or item.get("type") or "").lower()
            if "bild" in doc_type or "foto" in doc_type:
                defaults = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".gif"]
            elif "pdf" in doc_type:
                defaults = [".pdf"]
            elif "video" in doc_type:
                defaults = [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v"]
            elif "audio" in doc_type:
                defaults = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]
            elif "tabelle" in doc_type or "csv" in doc_type or "excel" in doc_type:
                defaults = [".csv", ".xlsx", ".xls", ".ods"]
            elif "text" in doc_type or "word" in doc_type:
                defaults = [".txt", ".docx", ".doc", ".rtf", ".odt", ".md"]
            else:
                defaults = []
            for suffix in defaults:
                if suffix not in suffixes:
                    suffixes.append(suffix)
        return suffixes

    def document_candidate_filenames(self, item: dict | None, preferred_name: str | None = None) -> list[str]:
        """Robuste Namensvarianten für vorhandene lokale Dateien bilden.

        Behandelt u. a. Altdaten wie ``name_jpg`` / ``name_jpg.jpg`` und fehlende
        Dateiendungen. Die Reihenfolge ist bewusst: zuerst DB-Wert, dann Varianten.
        """
        raw_names: list[str] = []
        if preferred_name:
            raw_names.append(str(preferred_name))
        if item:
            for key in ("current_filename", "stored_filename", "original_filename"):
                value = str(item.get(key) or "").strip()
                if value:
                    raw_names.append(Path(value).name)
            for key in ("current_path",):
                value = str(item.get(key) or "").strip()
                if value:
                    raw_names.append(Path(value).name)
        suffixes = self.document_candidate_suffixes(item)
        result: list[str] = []

        def add(name: str) -> None:
            name = (name or "").strip()
            if name and name not in result:
                result.append(name)

        for name in raw_names:
            add(name)
            path_name = Path(name)
            suffix = path_name.suffix.lower()
            if not suffix:
                for ext in suffixes:
                    add(name + ext)
                    token = ext.lstrip(".").lower()
                    lower = name.lower()
                    for sep in ("_", "-", " "):
                        tail = sep + token
                        if lower.endswith(tail):
                            add(name[: -len(tail)] + ext)
            else:
                token = suffix.lstrip(".").lower()
                lower_stem = path_name.stem.lower()
                for sep in ("_", "-", " "):
                    tail = sep + token
                    if lower_stem.endswith(tail):
                        add(path_name.stem[: -len(tail)] + suffix)
        return result

    def find_candidate_file_in_folder(self, folder: Path, item: dict | None, preferred_name: str | None = None) -> Path | None:
        if not folder.exists() or not folder.is_dir():
            return None
        for name in self.document_candidate_filenames(item, preferred_name):
            candidate = folder / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def resolve_document_local_path(self, item: dict | None) -> Path | None:
        """Findet die lokale Datei robust auch bei Altdaten/Pfaddifferenzen.

        MySQL speichert ggf. den lokalen Pfad des hochladenden Rechners. Auf einem
        anderen PC wird daraus über das eigene Nextcloud-Stammverzeichnis ein
        passender lokaler Pfad gebaut. Zusätzlich werden fehlende/verdoppelte
        Dateiendungen tolerant behandelt, z. B. ``datei_jpg`` -> ``datei_jpg.jpg``
        oder ``datei.jpg``.
        """
        if not item:
            return None

        for text in [item.get("current_path")]:
            if not text:
                continue
            try:
                p = Path(str(text))
                if p.exists() and p.is_file():
                    return p
                folder = p.parent
                found = self.find_candidate_file_in_folder(folder, item, p.name)
                if found:
                    return found
            except Exception:
                pass

        for text in [item.get("target_folder")]:
            if not text:
                continue
            try:
                p = Path(str(text))
                if p.exists() and p.is_file():
                    return p
                folder = p if p.exists() and p.is_dir() else p.parent
                found = self.find_candidate_file_in_folder(folder, item)
                if found:
                    return found
            except Exception:
                pass

        base_text = self.base_folder_var.get().strip()
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        if not base.exists():
            return None

        tokens = self.known_top_folder_tokens()
        for text in [item.get("current_path"), item.get("target_folder")]:
            if not text:
                continue
            parts = Path(str(text)).parts
            for i, part in enumerate(parts):
                if self.normalize_folder_token(part) in tokens:
                    rel_parts = parts[i:]
                    candidate = base.joinpath(*rel_parts)
                    if candidate.exists() and candidate.is_file():
                        return candidate
                    folder = candidate if candidate.exists() and candidate.is_dir() else candidate.parent
                    found = self.find_candidate_file_in_folder(folder, item, candidate.name)
                    if found:
                        return found

        for name in self.document_candidate_filenames(item):
            try:
                matches = list(base.rglob(name))
                if matches:
                    return matches[0]
            except Exception:
                pass
        return None

    def normalize_admin_item_path_for_current_pc(self, item: dict) -> None:
        path = self.resolve_document_local_path(item)
        if path:
            item["current_path"] = str(path)
            item["target_folder"] = str(path.parent)
