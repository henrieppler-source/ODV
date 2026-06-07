from __future__ import annotations

import unicodedata
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from .app_logging import app_log_exception
from .config import save_config
from .file_service import is_image_file
from .users import role_allows_admin


class PathPolicyManagerMixin:
    def api_role_to_local(self, role: str) -> str:
        mapping = {"ortschronist": "Ortschronist", "admin": "Admin", "superadmin": "Superadmin"}
        return mapping.get(str(role).strip().lower(), str(role).strip() or "Ortschronist")

    def local_role_to_api(self, role: str) -> str:
        mapping = {"Ortschronist": "ortschronist", "Admin": "admin", "Superadmin": "superadmin"}
        return mapping.get(str(role).strip(), "ortschronist")

    def normalize_folder_token(self, value: str) -> str:
        """Normiert Orts-/Ordnernamen für einfache Rechtefilter, z. B. Römhild -> roemhild."""
        text = str(value or "").strip().lower()
        replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return "".join(ch for ch in text if ch.isalnum())

    def top_level_folder_name(self, folder: Path, base: Path) -> str:
        try:
            rel = folder.relative_to(base)
            if str(rel) == ".":
                return "."
            return rel.parts[0] if rel.parts else "."
        except ValueError:
            return folder.name

    def is_odv_update_path(self, path: Path) -> bool:
        """Technischen Nextcloud-Updateordner aus normalen Ablage-/Auswahlbäumen ausblenden."""
        return any(str(part).strip().upper() == "ODV_UPDATE" for part in path.parts)

    def is_hidden_system_path(self, path: Path) -> bool:
        """Blendet technische Systemdateien aus normalen ODV-Bäumen aus."""
        name = str(path.name or "").strip()
        lower = name.lower()
        # Technische System-/Syncdateien konsequent aus normalen ODV-Bäumen ausblenden.
        if lower in {"desktop.ini", "thumbs.db", ".ds_store", ".nextcloudsync.log"}:
            return True
        if name.upper() == "_ARCHIV" or lower in {"archiv"}:
            return True
        if lower.endswith(".tmp") or lower.startswith("~$"):
            return True
        if lower.startswith(".sync_") and (lower.endswith(".db") or lower.endswith(".db-shm") or lower.endswith(".db-wal")):
            return True
        if name.startswith(".ortschronik_"):
            return True
        if self.is_odv_update_path(path):
            return True
        return False

    def normalize_search_text(self, value: str) -> str:
        """Normiert Suchbegriffe/Dateinamen: klein, ohne Umlaute/Sonderzeichen."""
        return self.normalize_folder_token(value)

    def default_folder_permissions(self) -> dict[str, dict[str, bool]]:
        role = self.current_role()
        if role in ("Admin", "Superadmin"):
            return {key: {"read": True, "write": True} for key, _ in self.FOLDER_GROUPS}
        defaults = {
            "00_ORTSCHRONIK": {"read": True, "write": False},
            "01_ABLAGE_ORTSCHRONIK": {"read": True, "write": True},
            "02_AUSTAUSCH": {"read": True, "write": True},
            "03_INFORMATION": {"read": True, "write": False},
            "05_ORGA_CHRONISTEN": {"read": False, "write": False},
            "06_UNSERE_ARBEITEN": {"read": True, "write": True},
            "OWN_PLACE_FOLDER": {"read": True, "write": True},
            "OTHER_PLACE_FOLDERS": {"read": False, "write": False},
        }
        return defaults

    def load_current_folder_permissions(self) -> None:
        """Lädt Rechte und Ortsordner-Stammdaten aus der API.

        Fallback: sinnvolle Standardrechte, damit die App auch weiterarbeitet,
        wenn die neue Rechte-API noch nicht installiert ist.
        """
        self.folder_permissions = self.default_folder_permissions()
        if self.api_token:
            try:
                response = self.api.get_folder_permissions(self.api_token)
                perms = response.get("permissions", [])
                loaded: dict[str, dict[str, bool]] = {}
                for row in perms:
                    key = str(row.get("folder_group", "")).strip()
                    if not key:
                        continue
                    loaded[key] = {
                        "read": bool(int(row.get("can_read", 0) or 0)),
                        "write": bool(int(row.get("can_write", 0) or 0)),
                    }
                if loaded:
                    self.folder_permissions.update(loaded)
            except Exception as exc:
                app_log_exception("Ordnerrechte konnten nicht aus API geladen werden", exc)
            try:
                response = self.api.list_place_folders(self.api_token)
                self.place_folder_map = {
                    self.normalize_folder_token(str(row.get("place", ""))): str(row.get("folder_name", "")).strip()
                    for row in response.get("places", []) if row.get("place") and row.get("folder_name")
                }
            except Exception as exc:
                app_log_exception("Ortsordner-Stammdaten konnten nicht aus API geladen werden", exc)
                self.place_folder_map = dict(self.config_data.get("place_folder_map", {}) or {})
        else:
            self.place_folder_map = dict(self.config_data.get("place_folder_map", {}) or {})

    def folder_permission_group(self, folder: Path, base: Path) -> str | None:
        """Ermittelt die fachliche Ordnergruppe auch dann, wenn die ODV-Struktur
        nicht direkt im Nextcloud-Stamm liegt, sondern z. B. unter
        Ortschronisten_Gemeinsam\00_ORTSCHRONIK.
        """
        try:
            rel_parts = folder.relative_to(base).parts
        except ValueError:
            rel_parts = folder.parts
        if not rel_parts:
            rel_parts = (folder.name,)

        fixed = [
            "00_ORTSCHRONIK",
            "01_ABLAGE_ORTSCHRONIK",
            "02_AUSTAUSCH",
            "03_INFORMATION",
            "05_ORGA_CHRONISTEN",
            "06_UNSERE_ARBEITEN",
        ]
        normalized_parts = [self.normalize_folder_token(part) for part in rel_parts]
        for name in fixed:
            token = self.normalize_folder_token(name)
            if token in normalized_parts:
                return name

        place_norm = self.normalize_folder_token(self.place_var.get())
        own_folder = self.place_folder_map.get(place_norm, "")
        own_token = self.normalize_folder_token(own_folder)
        if own_token and own_token in normalized_parts:
            return "OWN_PLACE_FOLDER"
        if place_norm and any(place_norm in part for part in normalized_parts):
            return "OWN_PLACE_FOLDER"

        known_place_folders = {self.normalize_folder_token(v) for v in self.place_folder_map.values() if v}
        for part, norm in zip(rel_parts, normalized_parts):
            if norm in known_place_folders:
                return "OTHER_PLACE_FOLDERS"
            if len(str(part)) >= 3 and str(part)[:2].isdigit() and "_" in str(part):
                return "OTHER_PLACE_FOLDERS"
        return None

    def folder_group_allowed(self, group: str | None, mode: str = "write") -> bool:
        if not group:
            return False
        perms = self.folder_permissions or self.default_folder_permissions()
        row = perms.get(group)
        if not row:
            return False
        return bool(row.get("write" if mode == "write" else "read", False))

    def default_upload_target(self) -> str | None:
        """Standardmäßig 01_ABLAGE_ORTSCHRONIK auswählen, falls erlaubt."""
        preferred = "01_ABLAGE_ORTSCHRONIK"
        for label, path in self.target_folder_map.items():
            try:
                if self.top_level_folder_name(path, Path(self.base_folder_var.get().strip()).expanduser()) == preferred:
                    return label
            except Exception:
                pass
        for label in self.target_folder_map:
            if label == preferred or label.startswith(preferred + "\\") or label.startswith(preferred + "/"):
                return label
        return next(iter(self.target_folder_map.keys()), None)

    def is_folder_allowed_for_current_user(self, folder: Path, base: Path) -> bool:
        """Schreibrecht für Zielordner nach eigener MySQL-Rechteverwaltung.

        Der lokale Nextcloud-Schreibtest bleibt technische Plausibilitätsprüfung.
        Die fachliche Freigabe erfolgt über Ordnergruppenrechte.
        """
        try:
            rel_parts = folder.relative_to(base).parts
            if (
                self.current_role() not in {"Admin", "Superadmin"}
                and rel_parts
                and self.normalize_folder_token(rel_parts[0]) == self.normalize_folder_token("Ortschronisten_Gemeinsam")
            ):
                return False
        except Exception:
            pass
        if self.is_odv_update_path(folder) or any(str(part).upper() == "_ARCHIV" for part in folder.parts):
            return False
        if self.current_role() == "Superadmin":
            return True
        group = self.folder_permission_group(folder, base)
        return self.folder_group_allowed(group, "write")

    def is_folder_readable_for_current_user(self, folder: Path, base: Path) -> bool:
        """Leserecht für Dateiansicht.

        00_ORTSCHRONIK ist der zentrale Lesebereich der Anwendung und wird in
        „Dateien anzeigen“ für alle Rollen vollständig rekursiv angezeigt.
        Schreibrechte werden davon nicht abgeleitet; Bearbeiten/Speichern wird
        separat geprüft. Technische Updateordner bleiben ausgeblendet.
        """
        if self.is_odv_update_path(folder):
            return False
        if self.current_role() == "Superadmin":
            return True
        group = self.folder_permission_group(folder, base)
        if group == "00_ORTSCHRONIK":
            return True
        return self.folder_group_allowed(group, "read")

    def is_file_view_path_in_readable_branch(self, path: Path, base: Path) -> bool:
        """True, wenn path in einem für „Dateien anzeigen“ lesbaren Bereich liegt.

        Wichtig für v77: Die Dateiansicht verwendet für Admins und Bearbeiter
        dieselbe physische Rekursion wie Superadmin. Gefiltert wird nur auf
        Ebene der ODV-Haupt-/Ortsbereiche. Sobald ein lesbarer Bereich erkannt
        ist, werden alle Unterordner darunter angezeigt.
        """
        if self.is_hidden_system_path(path):
            return False
        if self.current_role() == "Superadmin":
            return True
        try:
            rel_parts = path.relative_to(base).parts
        except Exception:
            rel_parts = path.parts
        if not rel_parts:
            return True

        fixed_names = [
            "00_ORTSCHRONIK",
            "01_ABLAGE_ORTSCHRONIK",
            "02_AUSTAUSCH",
            "03_INFORMATION",
            "05_ORGA_CHRONISTEN",
            "06_UNSERE_ARBEITEN",
            "06_ARBEIT_DER_ORTSCHRONISTEN",
        ]
        fixed_tokens = {self.normalize_folder_token(name): name for name in fixed_names}
        for part in rel_parts:
            token = self.normalize_folder_token(part)
            if token in fixed_tokens:
                group = fixed_tokens[token]
                if group in {"00_ORTSCHRONIK", "06_ARBEIT_DER_ORTSCHRONISTEN"}:
                    # 00_ORTSCHRONIK ist Lesebereich; 06_ARBEIT... als realer Ordnername
                    # auf die Rechtegruppe 06_UNSERE_ARBEITEN abbilden.
                    return True if group == "00_ORTSCHRONIK" else self.folder_group_allowed("06_UNSERE_ARBEITEN", "read")
                return self.folder_group_allowed(group, "read")

        # Ortsordner: eigener Ort lesen, andere Orte nur bei entsprechendem Recht.
        group = self.folder_permission_group(path if path.is_dir() else path.parent, base)
        return self.folder_group_allowed(group, "read")

    def can_edit_file_view_metadata(self, path: Path | None = None, item: dict | None = None) -> bool:
        path = path or self.file_view_current_path
        item = item or self.file_view_current_metadata or {}
        if self.is_current_admin():
            return True
        if not path:
            return False
        if item and self.is_selected_document_owner(item):
            return True
        try:
            base_text = str(self.base_folder_var.get() or "").strip()
            base = Path(base_text).expanduser() if base_text else None
        except Exception:
            base = None
        if base is not None:
            try:
                folder = path if path.is_dir() else path.parent
                if self.is_folder_allowed_for_current_user(folder, base):
                    return True
            except Exception:
                pass
        return self.is_selected_document_owner(item)
