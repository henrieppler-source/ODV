from __future__ import annotations

from pathlib import Path
import traceback
from importlib import util


def run_smoke_script(script_name: str) -> int:
    script = Path(__file__).resolve().parent / script_name
    if not script.exists():
        print(f"FEHLER: Script fehlt: {script}")
        return 2
    print(f"[{script_name}]")
    try:
        spec = util.spec_from_file_location(script_name.replace(".py", "_smoke"), str(script))
        if spec is None or spec.loader is None:
            print(f"FEHLER: Script konnte nicht geladen werden: {script}")
            return 2
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"[{script_name}] Ausführung fehlgeschlagen:")
        print(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    module_attrs = module.__dict__
    for entry in ("main", "run_smoke"):
        callback = module_attrs.get(entry)
        if not callable(callback):
            continue
        try:
            result = callback()
        except SystemExit as exc:
            return int(exc.code or 0)
        except Exception as exc:
            print(f"[{script_name}] {entry}()-Aufruf fehlgeschlagen:")
            print(f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
            return 1
        if isinstance(result, int):
            if result == 0:
                print(f"[{script_name}] {entry} OK")
                return 0
            print(f"[{script_name}] {entry} failed with {result}")
            return result
        print(f"[{script_name}] {entry} returned non-integer result: {result!r}")
    print(f"FEHLER: {script_name} hat keinen ausführbaren Entry-Point (main/run_smoke).")
    return 1


def main() -> int:
    checks = [
        "smoke_mail_dialog.py",
        "smoke_file_view_filter.py",
        "smoke_main_window.py",
    ]
    for script_name in checks:
        rc = run_smoke_script(script_name)
        if rc:
            return rc
    print("OK: Alle Kern-Smokes erfolgreich.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
