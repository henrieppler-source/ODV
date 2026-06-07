from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .app_logging import app_log, app_log_exception


class AppUpdateMixin:
    def app_version(self) -> str:
        return str(self.APP_VERSION or "v0")

    def is_frozen_runtime(self) -> bool:
        try:
            return bool(sys.frozen)
        except Exception:
            return False

    def app_short_name(self) -> str:
        return str(self.APP_SHORT_NAME or "ODV")

    def parse_version_number(self, version: str) -> int:
        """Extrahiert die führende ODV-Versionsnummer aus Strings wie v69."""
        text = str(version or "").strip().lower().lstrip("v")
        digits = "".join(ch for ch in text if ch.isdigit())
        try:
            return int(digits or 0)
        except Exception:
            return 0

    def is_newer_version(self, remote_version: str, local_version: str | None = None) -> bool:
        return self.parse_version_number(remote_version) > self.parse_version_number(local_version or self.app_version())

    def get_app_update_info(self) -> dict:
        """Liest die freigegebene App-Version aus der API."""
        try:
            resp = self.api.app_update(self.api_token or None)
            info = resp.get("update") or resp.get("release") or resp
            return info if isinstance(info, dict) else {}
        except Exception:
            raise

    def default_update_target_dir(self, version: str) -> Path:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return root / "ODV" / "versions" / str(version).strip()

    def update_attempt_marker_path(self) -> Path:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return root / "ODV" / "updates" / "last_update_attempt.json"

    def write_update_attempt_marker(self, update: dict, source_dir: Path, target_dir: Path) -> None:
        """Merkt sich einen gestarteten Updateversuch, damit eine fehlgeschlagene Installation keine Endlosschleife auslöst."""
        try:
            marker = self.update_attempt_marker_path()
            marker.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "from_version": self.app_version(),
                "to_version": str(update.get("version") or ""),
                "file_name": str(update.get("file_name") or update.get("file") or ""),
                "source_dir": str(source_dir),
                "target_dir": str(target_dir),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            }
            marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def read_update_attempt_marker(self) -> dict:
        try:
            marker = self.update_attempt_marker_path()
            if marker.exists():
                data = json.loads(marker.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def has_recent_update_attempt(self, latest_version: str, max_minutes: int = 30) -> bool:
        """Verhindert Update-Endlosschleifen nach einem fehlgeschlagenen oder unvollständigen Selbstupdate."""
        data = self.read_update_attempt_marker()
        if str(data.get("to_version") or "").strip() != str(latest_version or "").strip():
            return False
        started = str(data.get("started_at") or "")
        try:
            dt = datetime.fromisoformat(started)
            age = (datetime.now() - dt).total_seconds() / 60.0
            return 0 <= age <= max_minutes
        except Exception:
            return True

    def resolve_nextcloud_update_source(self, update: dict) -> Path | None:
        """Ermittelt die lokale Nextcloud-Quelle der freigegebenen Update-Datei."""
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            return None
        base = Path(base_text).expanduser()
        rel = str(update.get("nextcloud_relative_path") or update.get("path") or update.get("file_path") or "").strip()
        file_name = str(update.get("file_name") or update.get("file") or "").strip()
        candidates: list[Path] = []
        if rel:
            rel_path = Path(rel.replace("/", os.sep).replace("\\", os.sep))
            candidates.append(base / rel_path)
            if file_name and rel_path.name.lower() != file_name.lower():
                candidates.append(base / rel_path / file_name)
        if file_name:
            candidates.append(base / "02_AUSTAUSCH" / "ODV_UPDATE" / "Windows" / file_name)
            candidates.append(base / "02_AUSTAUSCH" / "ODV_UPDATE" / file_name)
            candidates.append(base / "AUSTAUSCH" / "ODV_UPDATE" / "Windows" / file_name)
            candidates.append(base / "AUSTAUSCH" / "ODV_UPDATE" / file_name)
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    return candidate
            except Exception:
                pass
        return None

    def sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def safe_extract_zip(self, zf: zipfile.ZipFile, extract_dir: Path) -> None:
        """Extrahiert ein ZIP nur innerhalb des Zielordners."""
        base_dir = extract_dir.resolve()
        for member in zf.infolist():
            target = (extract_dir / member.filename).resolve()
            try:
                common = os.path.commonpath([str(base_dir), str(target)])
            except Exception as exc:
                raise RuntimeError(f"Ungültiger ZIP-Pfad: {member.filename}") from exc
            if common != str(base_dir):
                raise RuntimeError(f"Unsicherer ZIP-Pfad blockiert: {member.filename}")
            zf.extract(member, extract_dir)

    def stage_app_update(self, update: dict) -> Path:
        """Kopiert/entpackt die freigegebene Version aus dem lokalen Nextcloud-Syncordner."""
        version = str(update.get("version") or "").strip()
        if not version:
            raise RuntimeError("Die Updatefreigabe enthält keine Versionsnummer.")
        source = self.resolve_nextcloud_update_source(update)
        if not source:
            raise RuntimeError("Die freigegebene Update-Datei wurde im lokalen Nextcloud-Ordner nicht gefunden. Bitte Nextcloud-Sync prüfen.")
        expected_hash = str(update.get("sha256") or "").strip().lower()
        if expected_hash:
            actual_hash = self.sha256_file(source).lower()
            if actual_hash != expected_hash:
                raise RuntimeError("Die Prüfsumme der Update-Datei stimmt nicht. Update wird nicht installiert.")
        target_dir = self.default_update_target_dir(version)
        target_dir.mkdir(parents=True, exist_ok=True)
        staged_file = target_dir / source.name
        shutil.copy2(source, staged_file)
        if expected_hash:
            staged_hash = self.sha256_file(staged_file).lower()
            if staged_hash != expected_hash:
                raise RuntimeError("Die kopierte Update-Datei ist fehlerhaft. Prüfsumme stimmt nicht.")
        if staged_file.suffix.lower() == ".zip":
            extract_dir = target_dir / "entpackt"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_file, "r") as zf:
                self.safe_extract_zip(zf, extract_dir)
            exe_matches = list(extract_dir.rglob("ODV.exe")) + list(extract_dir.rglob("*.exe"))
            return exe_matches[0] if exe_matches else extract_dir
        return staged_file

    def current_install_dir(self) -> Path:
        """Ermittelt den Programmordner, der vom Komfort-Updater ersetzt werden soll."""
        if self.is_frozen_runtime():
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    def find_updater_executable(self) -> Path | None:
        """Sucht die mitgelieferte ODV_Updater.exe bzw. das Python-Updaterscript im Entwicklungsmodus."""
        install_dir = self.current_install_dir()
        candidates = [
            install_dir / "ODV_Updater.exe",
            install_dir / "updater" / "ODV_Updater.exe",
            Path(sys.executable).resolve().parent / "ODV_Updater.exe" if self.is_frozen_runtime() else None,
        ]
        for candidate in candidates:
            if candidate and candidate.exists() and candidate.is_file():
                return candidate
        dev_script = Path(__file__).resolve().parent.parent / "launcher_updater.py"
        if dev_script.exists():
            return dev_script
        return None

    def resolve_prepared_update_root(self, prepared: Path) -> Path:
        """Ermittelt aus stage_app_update() den Quellordner, aus dem die neue Version kopiert wird."""
        prepared = Path(prepared)
        if prepared.is_file():
            if prepared.name.lower() == "odv.exe":
                return prepared.parent
            return prepared.parent
        return prepared

    def launch_comfort_updater(self, prepared: Path, update: dict) -> None:
        """Startet den separaten Komfort-Updater und beendet die laufende ODV-Instanz."""
        updater = self.find_updater_executable()
        if not updater:
            raise RuntimeError("ODV_Updater.exe wurde nicht gefunden. Bitte Buildpaket vollständig verteilen.")

        source_dir = self.resolve_prepared_update_root(Path(prepared)).resolve()
        target_dir = self.current_install_dir().resolve()
        if not source_dir.exists():
            raise RuntimeError("Der vorbereitete Updateordner wurde nicht gefunden.")
        if not target_dir.exists():
            raise RuntimeError("Der aktuelle Programmordner wurde nicht gefunden.")
        if source_dir == target_dir:
            raise RuntimeError("Updatequelle und Programmordner sind identisch. Update wird abgebrochen, um die Installation nicht zu beschädigen.")
        self.write_update_attempt_marker(update, source_dir, target_dir)

        plan_dir = Path(os.environ.get("TEMP") or tempfile.gettempdir()) / "ODV" / "updates"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / f"odv_update_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        plan = {
            "app_name": self.app_short_name(),
            "from_version": self.app_version(),
            "to_version": str(update.get("version") or ""),
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "main_exe": "ODV.exe",
            "wait_pid": os.getpid(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        if updater.suffix.lower() == ".py":
            cmd = [sys.executable, str(updater), str(plan_path)]
        else:
            temp_updater_dir = plan_dir / "updater_runtime"
            if temp_updater_dir.exists():
                shutil.rmtree(temp_updater_dir, ignore_errors=True)
            temp_updater_dir.mkdir(parents=True, exist_ok=True)
            temp_updater = temp_updater_dir / "ODV_Updater.exe"
            shutil.copy2(updater, temp_updater)
            runtime_internal = updater.parent / "_internal"
            if runtime_internal.exists() and runtime_internal.is_dir():
                shutil.copytree(runtime_internal, temp_updater_dir / "_internal", dirs_exist_ok=True)
            else:
                raise RuntimeError("_internal-Laufzeitordner für ODV_Updater.exe wurde nicht gefunden. Bitte den vollständigen dist\\ODV-Ordner verwenden.")
            cmd = [str(temp_updater), str(plan_path)]

        messagebox.showinfo(
            "ODV-Update",
            "Das Update ist vorbereitet.\n\n"
            "Nach Klick auf OK wird ODV geschlossen. Anschließend startet der Updater, "
            "ersetzt den Programmordner und startet die neue Version.",
            parent=self,
        )
        subprocess.Popen(cmd, shell=False, cwd=str(plan_dir))
        try:
            self.quit()
            self.destroy()
        finally:
            os._exit(0)

    def check_app_update_on_startup(self) -> None:
        try:
            self.check_app_update(interactive=False)
        except Exception as exc:
            app_log_exception("ODV-Updateprüfung beim Start fehlgeschlagen", exc)

    def check_app_update(self, interactive: bool = False) -> None:
        """Prüft die freigegebene ODV-Version und bietet Kopie/Entpacken aus Nextcloud an."""
        try:
            update = self.get_app_update_info()
        except Exception as exc:
            if interactive:
                messagebox.showerror("ODV-Update", f"Updateinformation konnte nicht abgerufen werden:\n{exc}", parent=self)
            return
        if not update or not update.get("version"):
            if interactive:
                messagebox.showinfo("ODV-Update", "Es ist keine Updatefreigabe hinterlegt.", parent=self)
            return
        latest = str(update.get("version") or "").strip()
        if not self.is_newer_version(latest):
            if interactive:
                messagebox.showinfo("ODV-Update", f"Keine neuere Version freigegeben.\n\nLokal: {self.app_version()}\nFreigegeben: {latest}", parent=self)
            return
        if self.has_recent_update_attempt(latest):
            hint = (
                f"Für Version {latest} wurde vor Kurzem bereits ein Updateversuch gestartet.\n\n"
                "ODV bietet dasselbe Update nicht erneut automatisch an, damit keine Endlosschleife entsteht. "
                "Bitte prüfen Sie den Updater-Log unter %TEMP%\\ODV\\updates\\odv_updater.log "
                "und starten Sie die Updateprüfung danach manuell über Hilfe → Nach ODV-Update suchen..."
            )
            if interactive:
                if not messagebox.askyesno("ODV-Update", hint + "\n\nTrotzdem erneut versuchen?", parent=self):
                    return
            else:
                app_log("warning", "Updateangebot wegen kürzlichem Updateversuch unterdrückt", latest=latest)
                return

        required = bool(update.get("required"))
        notes = str(update.get("release_notes") or update.get("notes") or "").strip()
        file_name = str(update.get("file_name") or update.get("file") or "").strip()
        msg = f"Eine neue ODV-Version ist verfügbar.\n\nLokal: {self.app_version()}\nNeu: {latest}\nDatei: {file_name or '-'}"
        if required:
            msg += "\n\nDieses Update ist als Pflichtupdate markiert."
        if notes:
            msg += f"\n\nHinweise:\n{notes[:1200]}"
        msg += "\n\nDie neue Version wird aus dem lokalen Nextcloud-Updateordner kopiert. Danach startet der ODV-Updater, beendet diese Sitzung, ersetzt den Programmordner und startet die neue ODV-Version."
        button_text = "Pflichtupdate jetzt installieren?" if required else "Update jetzt installieren?"
        if not messagebox.askyesno("ODV-Update verfügbar", msg + "\n\n" + button_text, parent=self):
            if required:
                messagebox.showwarning("Pflichtupdate", "Dieses Update ist als Pflichtupdate markiert. Die Anwendung sollte erst nach Aktualisierung weiter genutzt werden.", parent=self)
            return
        try:
            prepared = self.stage_app_update(update)
            self.launch_comfort_updater(prepared, update)
        except Exception as exc:
            messagebox.showerror("ODV-Update", f"Update konnte nicht installiert werden:\n{exc}", parent=self)

    def open_app_update_admin_dialog(self) -> None:
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Funktion ist nur für Superadmins freigegeben.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("ODV-Updatefreigabe verwalten")
        try:
            self.track_window_geometry(dialog, "ODV-Updatefreigabe verwalten")
        except Exception:
            pass
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        frame = ttk.Frame(dialog, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        current = {}
        try:
            current = self.get_app_update_info()
        except Exception:
            current = {}
        version_var = tk.StringVar(value=str(current.get("version") or ""))
        file_var = tk.StringVar(value=str(current.get("file_name") or current.get("file") or ""))
        path_var = tk.StringVar(value=str(current.get("nextcloud_relative_path") or current.get("path") or "02_AUSTAUSCH/ODV_UPDATE/Windows/"))
        sha_var = tk.StringVar(value=str(current.get("sha256") or ""))
        required_var = tk.BooleanVar(value=bool(current.get("required")))
        notes_text = tk.Text(frame, width=76, height=6, wrap="word")
        fields = [
            ("Freigegebene Version:", version_var),
            ("Dateiname:", file_var),
            ("Nextcloud-Relativpfad:", path_var),
            ("SHA256-Prüfsumme:", sha_var),
        ]
        for r, (label, var) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=var, width=72).grid(row=r, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(frame, text="Pflichtupdate", variable=required_var).grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="Release-Hinweise:").grid(row=5, column=0, sticky="nw", pady=4)
        notes_text.grid(row=5, column=1, sticky="ew", pady=4)
        notes_text.insert("1.0", str(current.get("release_notes") or current.get("notes") or ""))
        hint = "Standardordner: 02_AUSTAUSCH/ODV_UPDATE/Windows. Mit 'Updatepaket vorbereiten' wird die Datei dorthin kopiert und die SHA256-Prüfsumme automatisch eingetragen."
        ttk.Label(frame, text=hint, wraplength=620).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 4))

        def prepare_update_package() -> None:
            source_text = filedialog.askopenfilename(
                title="ODV-Updatepaket auswählen",
                parent=dialog,
                filetypes=[
                    ("Updatepakete", "*.zip *.exe *.msi"),
                    ("ZIP-Dateien", "*.zip"),
                    ("Programme", "*.exe"),
                    ("Installer", "*.msi"),
                    ("Alle Dateien", "*.*"),
                ],
            )
            if not source_text:
                return
            base = self.nextcloud_base_path(show_message=True)
            if base is None:
                return
            source = Path(source_text).expanduser()
            if not source.exists() or not source.is_file():
                messagebox.showwarning("ODV-Update", f"Die ausgewählte Datei wurde nicht gefunden:\n{source}", parent=dialog)
                return
            relative_folder = Path("02_AUSTAUSCH") / "ODV_UPDATE" / "Windows"
            target_dir = base / relative_folder
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                messagebox.showerror("ODV-Update", f"Updateordner konnte nicht angelegt werden:\n{target_dir}\n\n{exc}", parent=dialog)
                return
            target = target_dir / source.name
            try:
                same_file = source.resolve() == target.resolve()
            except Exception:
                same_file = False
            if target.exists() and not same_file:
                if not messagebox.askyesno(
                    "ODV-Update",
                    f"Die Datei existiert im Updateordner bereits:\n{target}\n\nSoll sie überschrieben werden?",
                    parent=dialog,
                ):
                    return
            try:
                if not same_file:
                    shutil.copy2(source, target)
                checksum = self.sha256_file(target)
            except Exception as exc:
                messagebox.showerror("ODV-Update", f"Updatepaket konnte nicht vorbereitet werden:\n{exc}", parent=dialog)
                return

            file_var.set(target.name)
            path_var.set(relative_folder.as_posix())
            sha_var.set(checksum)
            if not version_var.get().strip():
                match = re.search(r"v\d+(?:[._-]\d+)?", target.stem, re.IGNORECASE)
                if match:
                    version_var.set(match.group(0).replace("_", ".").replace("-", ".").lower())
            messagebox.showinfo(
                "ODV-Update",
                "Updatepaket wurde vorbereitet.\n\n"
                f"Datei: {target.name}\n"
                f"Ordner: {relative_folder.as_posix()}\n"
                "Die Freigabe ist noch nicht gespeichert.",
                parent=dialog,
            )

        def calculate_hash_for_configured_file() -> None:
            base = self.nextcloud_base_path(show_message=True)
            if base is None:
                return
            file_name = file_var.get().strip()
            rel_text = path_var.get().strip()
            if not file_name and not rel_text:
                messagebox.showwarning("ODV-Update", "Bitte zuerst Dateiname oder Relativpfad eintragen.", parent=dialog)
                return
            rel_path = Path(rel_text.replace("\\", "/")) if rel_text else Path()
            candidates: list[Path] = []
            if rel_path.name and rel_path.suffix and not file_name:
                candidates.append(base / rel_path)
            elif rel_text and file_name:
                candidates.append(base / rel_path / file_name)
            if file_name:
                candidates.append(base / "02_AUSTAUSCH" / "ODV_UPDATE" / "Windows" / file_name)
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    try:
                        sha_var.set(self.sha256_file(candidate))
                        if not path_var.get().strip():
                            path_var.set("02_AUSTAUSCH/ODV_UPDATE/Windows")
                        messagebox.showinfo("ODV-Update", f"SHA256-Prüfsumme wurde berechnet:\n{candidate}", parent=dialog)
                    except Exception as exc:
                        messagebox.showerror("ODV-Update", f"Prüfsumme konnte nicht berechnet werden:\n{exc}", parent=dialog)
                    return
            messagebox.showwarning("ODV-Update", "Die konfigurierte Updatedatei wurde im lokalen Nextcloud-Ordner nicht gefunden.", parent=dialog)

        def save_release() -> None:
            payload = {
                "version": version_var.get().strip(),
                "file_name": file_var.get().strip(),
                "nextcloud_relative_path": path_var.get().strip(),
                "sha256": sha_var.get().strip(),
                "required": bool(required_var.get()),
                "release_notes": notes_text.get("1.0", "end").strip(),
            }
            if not payload["version"]:
                messagebox.showwarning("ODV-Update", "Bitte eine Version eintragen.", parent=dialog)
                return
            if not payload["file_name"] and not payload["nextcloud_relative_path"]:
                messagebox.showwarning("ODV-Update", "Bitte Dateiname oder Relativpfad eintragen.", parent=dialog)
                return
            try:
                self.api.update_app_release(self.api_token, payload)
                messagebox.showinfo("ODV-Update", "Updatefreigabe wurde gespeichert.", parent=dialog)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("ODV-Update", f"Updatefreigabe konnte nicht gespeichert werden:\n{exc}", parent=dialog)

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=1, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Updatepaket vorbereiten...", command=prepare_update_package).pack(side="left", padx=4)
        ttk.Button(buttons, text="SHA256 berechnen", command=calculate_hash_for_configured_file).pack(side="left", padx=4)
        ttk.Button(buttons, text="Lokal prüfen", command=lambda: self.check_app_update(interactive=True)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Speichern", command=save_release).pack(side="left", padx=4)
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="left", padx=4)
