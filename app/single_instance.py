from __future__ import annotations

import os
import sys
from pathlib import Path

_SINGLE_INSTANCE_LOCK_HANDLE = None


def _odv_lock_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    lock_dir = root / "ODV"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "odv_app.lock"


def acquire_single_instance_lock() -> bool:
    """Verhindert, dass ODV versehentlich zweimal parallel läuft."""
    global _SINGLE_INSTANCE_LOCK_HANDLE
    if os.environ.get("ODV_DISABLE_SINGLE_INSTANCE") == "1":
        return True
    try:
        lock_path = _odv_lock_path()
        fh = open(lock_path, "a+", encoding="utf-8")
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                return False
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                return False
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _SINGLE_INSTANCE_LOCK_HANDLE = fh
        return True
    except Exception:
        return True


def release_single_instance_lock() -> None:
    global _SINGLE_INSTANCE_LOCK_HANDLE
    fh = _SINGLE_INSTANCE_LOCK_HANDLE
    if fh is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fh.close()
    except Exception:
        pass
    _SINGLE_INSTANCE_LOCK_HANDLE = None


def resource_path(relative_path: str) -> Path:
    """Pfad zu mitgelieferten Ressourcen, kompatibel mit PyInstaller."""
    is_frozen = False
    try:
        is_frozen = bool(sys.frozen)
    except Exception:
        is_frozen = False
    if is_frozen:
        try:
            return Path(sys._MEIPASS) / relative_path
        except Exception:
            return Path(__file__).resolve().parent.parent / relative_path
    return Path(__file__).resolve().parent.parent / relative_path
