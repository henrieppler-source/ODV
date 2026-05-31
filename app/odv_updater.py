from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # Tk ist im PyInstaller-Build vorhanden; Fallback nur zur Sicherheit.
    tk = None
    messagebox = None

SKIP_NAMES = set()


def hidden_subprocess_kwargs() -> dict:
    """Verhindert sichtbare Konsolen-/Eingabefenster bei Hilfsaufrufen unter Windows."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def log_line(log_file: Path, message: str) -> None:
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + message + "\n")
    except Exception:
        pass


class UpdaterWindow:
    """Kleines sichtbares Fortschrittsfenster für den ODV-Komfort-Updater."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.root = None
        self.status_var = None
        self.detail_var = None
        self.step_var = None
        self._closed = False

        if tk is None:
            return
        try:
            self.root = tk.Tk()
            self.root.title("ODV wird aktualisiert")
            self.root.resizable(False, False)
            self.root.protocol("WM_DELETE_WINDOW", self._ignore_close)

            frame = tk.Frame(self.root, padx=18, pady=16)
            frame.pack(fill="both", expand=True)

            title = tk.Label(frame, text="ODV-Update läuft...", font=("TkDefaultFont", 11, "bold"), anchor="w")
            title.pack(fill="x", pady=(0, 10))

            self.step_var = tk.StringVar(value="Vorbereitung")
            self.status_var = tk.StringVar(value="Der Updater wird gestartet.")
            self.detail_var = tk.StringVar(value="Bitte ODV nicht manuell starten oder schließen.")

            tk.Label(frame, textvariable=self.step_var, anchor="w", font=("TkDefaultFont", 10, "bold")).pack(fill="x")
            tk.Label(frame, textvariable=self.status_var, anchor="w", justify="left", wraplength=620).pack(fill="x", pady=(6, 0))
            tk.Label(frame, textvariable=self.detail_var, anchor="w", justify="left", wraplength=620, fg="#555555").pack(fill="x", pady=(8, 0))

            steps = (
                "1. Alte ODV-Version beenden\n"
                "2. Updatepaket prüfen\n"
                "3. Programmdateien ersetzen\n"
                "4. Neue ODV-Version starten"
            )
            tk.Label(frame, text=steps, anchor="w", justify="left").pack(fill="x", pady=(14, 0))

            self.root.update_idletasks()
            width = 700
            height = 310
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, int((sw - width) / 2))
            y = max(0, int((sh - height) / 2))
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(800, lambda: self.root.attributes("-topmost", False))
            self.pump()
        except Exception as exc:
            log_line(self.log_file, f"WARNUNG: Updater-Fenster konnte nicht erstellt werden: {exc}")
            self.root = None

    def _ignore_close(self) -> None:
        # Während des Updates soll der Benutzer das Fenster nicht versehentlich schließen.
        self.update("Update läuft", "Bitte warten.", "Das Fenster schließt sich nach Abschluss automatisch.")

    def pump(self) -> None:
        if self.root is None or self._closed:
            return
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            self._closed = True

    def update(self, step: str, status: str, detail: str = "") -> None:
        log_line(self.log_file, f"STATUS: {step} - {status} {detail}".strip())
        if self.root is None or self._closed:
            return
        try:
            if self.step_var is not None:
                self.step_var.set(step)
            if self.status_var is not None:
                self.status_var.set(status)
            if self.detail_var is not None:
                self.detail_var.set(detail or "Bitte warten...")
            self.pump()
        except Exception:
            self._closed = True

    def finish(self, status: str, detail: str = "") -> None:
        self.update("Update abgeschlossen", status, detail)
        if self.root is not None and not self._closed:
            try:
                self.root.after(1200, self.root.destroy)
                deadline = time.time() + 1.5
                while time.time() < deadline:
                    self.pump()
                    time.sleep(0.05)
            except Exception:
                pass
            self._closed = True

    def fail(self, error: str, log_file: Path) -> None:
        self.update("Update fehlgeschlagen", "Das Update konnte nicht abgeschlossen werden.", f"Details siehe Logdatei:\n{log_file}\n\n{error}")
        if self.root is not None and not self._closed:
            try:
                if messagebox is not None:
                    messagebox.showerror(
                        "ODV-Update fehlgeschlagen",
                        "Das Update konnte nicht abgeschlossen werden.\n\n"
                        "Die bisherige Version bleibt erhalten, soweit sie nicht bereits ersetzt wurde.\n\n"
                        f"Details siehe Logdatei:\n{log_file}\n\n{error}",
                        parent=self.root,
                    )
                self.root.destroy()
            except Exception:
                pass
            self._closed = True


def write_update_result(plan: dict, target_dir: Path, exe_path: Path, log_file: Path) -> None:
    try:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        result_dir = Path(local) / "ODV" / "updates"
        result_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "to_version": str(plan.get("to_version") or ""),
            "target_dir": str(target_dir),
            "exe_path": str(exe_path),
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "started_after_update",
        }
        (result_dir / "last_update_result.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log_line(log_file, f"Update-Ergebnis-Marker geschrieben: {result_dir / 'last_update_result.json'}")
    except Exception as exc:
        log_line(log_file, f"WARNUNG: Update-Ergebnis-Marker konnte nicht geschrieben werden: {exc}")


def wait_for_process(pid: int, timeout: int, log_file: Path, ui: UpdaterWindow | None = None) -> None:
    if pid <= 0:
        return
    log_line(log_file, f"Warte auf ODV-Prozess PID {pid}.")
    if ui:
        ui.update("1. Alte ODV-Version beenden", "Warte auf das Beenden der alten ODV-Version...", f"Prozess-ID: {pid}")

    def is_running() -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
                **hidden_subprocess_kwargs(),
            )
            return str(pid) in (result.stdout or "")
        except Exception:
            return False

    deadline = time.time() + max(5, timeout)
    while time.time() < deadline:
        if ui:
            ui.pump()
        if not is_running():
            log_line(log_file, "ODV-Prozess ist beendet.")
            if ui:
                ui.update("1. Alte ODV-Version beenden", "Alte ODV-Version wurde beendet.", "Das Update kann fortgesetzt werden.")
            return
        time.sleep(0.5)

    log_line(log_file, f"ODV-Prozess PID {pid} läuft noch; versuche taskkill.")
    if ui:
        ui.update("1. Alte ODV-Version beenden", "ODV reagiert noch. Die alte Instanz wird jetzt gezielt beendet...", "Das ist normal, wenn Windows Dateien noch kurz festhält.")
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        log_line(log_file, f"WARNUNG: taskkill fehlgeschlagen: {exc}")

    for _ in range(20):
        if ui:
            ui.pump()
        if not is_running():
            log_line(log_file, "ODV-Prozess nach taskkill beendet.")
            return
        time.sleep(0.5)

    raise RuntimeError(f"Alte ODV-Instanz PID {pid} konnte nicht beendet werden. Update abgebrochen.")



def kill_remaining_odv_processes(log_file: Path, ui: UpdaterWindow | None = None) -> None:
    """Sicherheitsnetz: vor dem Kopieren keine alte ODV.exe weiterlaufen lassen.

    Der eigentliche Weg ist das Warten auf die konkrete PID. In der Praxis können
    nach PyInstaller-/Tkinter-Beendigung aber noch kurze Restprozesse bzw. eine
    zweite versehentlich gestartete Instanz existieren. ODV_Updater.exe ist davon
    nicht betroffen, weil sie anders heißt.
    """
    if os.name != "nt":
        return
    try:
        if ui:
            ui.update("1. Alte ODV-Version beenden", "Prüfe, ob noch ODV-Instanzen laufen...", "Gegebenenfalls werden alte ODV.exe-Prozesse beendet.")
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ODV.exe"],
            capture_output=True,
            text=True,
            timeout=8,
            **hidden_subprocess_kwargs(),
        )
        if "ODV.exe" not in (result.stdout or ""):
            log_line(log_file, "Keine weiteren ODV.exe-Prozesse gefunden.")
            return
        log_line(log_file, "Weitere ODV.exe-Prozesse gefunden; führe taskkill /IM ODV.exe aus.")
        subprocess.run(
            ["taskkill", "/IM", "ODV.exe", "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=12,
            **hidden_subprocess_kwargs(),
        )
        time.sleep(1.0)
    except Exception as exc:
        log_line(log_file, f"WARNUNG: Prüfung/Beenden weiterer ODV.exe-Prozesse fehlgeschlagen: {exc}")

def copy_tree(source: Path, target: Path, log_file: Path, ui: UpdaterWindow | None = None) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"Quellordner fehlt: {source}")
    target.mkdir(parents=True, exist_ok=True)
    skip_lower = {name.lower() for name in SKIP_NAMES}
    items = list(source.iterdir())
    total = len(items)
    for idx, item in enumerate(items, start=1):
        if ui:
            ui.update("3. Programmdateien ersetzen", f"Kopiere Dateien... ({idx}/{total})", item.name)
        if item.name.lower() in skip_lower:
            continue
        dst = target / item.name
        if item.is_dir():
            copy_tree(item, dst, log_file, ui=ui)
        else:
            try:
                if dst.exists():
                    dst.unlink()
                shutil.copy2(item, dst)
                log_line(log_file, f"Kopiert: {item} -> {dst}")
            except PermissionError as exc:
                raise RuntimeError(f"Datei ist noch gesperrt und konnte nicht ersetzt werden: {dst}") from exc


def validate_update_source(source_dir: Path, log_file: Path, ui: UpdaterWindow | None = None, label: str = "Updatepaket") -> None:
    """Prüft, ob ein entpacktes Updatepaket wie ein vollständiger PyInstaller-One-Dir-Build aussieht."""
    if ui:
        ui.update("2. Updatepaket prüfen", f"{label} wird geprüft...", str(source_dir))
    required_main = source_dir / "ODV.exe"
    required_updater = source_dir / "ODV_Updater.exe"
    internal_dir = source_dir / "_internal"
    if not required_main.exists():
        raise RuntimeError(f"{label} unvollständig: ODV.exe fehlt in {source_dir}")
    if not required_updater.exists():
        raise RuntimeError(f"{label} unvollständig: ODV_Updater.exe fehlt in {source_dir}")
    if not internal_dir.exists() or not internal_dir.is_dir():
        raise RuntimeError(f"{label} unvollständig: _internal-Ordner fehlt in {source_dir}")
    python_dlls = list(internal_dir.glob("python*.dll"))
    if not python_dlls:
        raise RuntimeError(f"{label} unvollständig: python*.dll fehlt in {internal_dir}")
    log_line(log_file, f"{label} geprüft: ODV.exe, ODV_Updater.exe und _internal/python*.dll vorhanden.")


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    plan_path = Path(sys.argv[1]).expanduser().resolve()
    log_file = plan_path.parent / "odv_updater.log"
    ui = UpdaterWindow(log_file)
    try:
        ui.update("Vorbereitung", "Lese Updateplan...", str(plan_path))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        source_dir = Path(plan["source_dir"]).expanduser().resolve()
        target_dir = Path(plan["target_dir"]).expanduser().resolve()
        main_exe = str(plan.get("main_exe") or "ODV.exe")
        wait_pid = int(plan.get("wait_pid") or 0)

        log_line(log_file, f"Starte Update {plan.get('from_version')} -> {plan.get('to_version')}.")
        log_line(log_file, f"Quelle: {source_dir}")
        log_line(log_file, f"Ziel: {target_dir}")
        ui.update("Vorbereitung", f"Update {plan.get('from_version')} → {plan.get('to_version')} wird vorbereitet.", "Bitte warten. ODV wird automatisch neu gestartet.")

        validate_update_source(source_dir, log_file, ui=ui, label="Updatepaket")
        wait_for_process(wait_pid, timeout=45, log_file=log_file, ui=ui)
        kill_remaining_odv_processes(log_file, ui=ui)
        time.sleep(1)
        if source_dir == target_dir:
            raise RuntimeError("Quelle und Ziel sind identisch; Update abgebrochen.")

        ui.update("3. Programmdateien ersetzen", "Programmordner wird aktualisiert...", "Bitte den Computer nicht ausschalten.")
        copy_tree(source_dir, target_dir, log_file, ui=ui)
        validate_update_source(target_dir, log_file, ui=ui, label="Zielordner")
        try:
            (target_dir / "odv_installed_version.txt").write_text(str(plan.get("to_version") or ""), encoding="utf-8")
        except Exception:
            pass
        log_line(log_file, "Dateien ersetzt und Zielordner geprüft.")

        exe_path = target_dir / main_exe
        if exe_path.exists():
            write_update_result(plan, target_dir, exe_path, log_file)
            env = os.environ.copy()
            env["ODV_SKIP_UPDATE_CHECK_ONCE"] = "1"
            ui.update("4. Neue ODV-Version starten", "Update erfolgreich. Neue ODV-Version wird gestartet...", str(exe_path))
            subprocess.Popen([str(exe_path), "--odv-skip-update-check-once"], shell=False, cwd=str(target_dir), env=env, **hidden_subprocess_kwargs())
            log_line(log_file, f"Neue ODV-Version gestartet: {exe_path} (Updateprüfung für diesen Start übersprungen)")
            ui.finish("Update erfolgreich abgeschlossen.", "ODV wird jetzt neu gestartet.")
        else:
            log_line(log_file, f"WARNUNG: Startdatei nicht gefunden: {exe_path}")
            ui.finish("Update kopiert, aber ODV.exe wurde nicht gefunden.", str(exe_path))
        return 0
    except Exception as exc:
        log_line(log_file, f"FEHLER: {exc}")
        ui.fail(str(exc), log_file)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
