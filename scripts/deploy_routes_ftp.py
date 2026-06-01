from __future__ import annotations

import ftplib
import posixpath
import re
from datetime import datetime
from pathlib import Path

from app.app_constants import APP_VERSION
from app.config import load_config
from app.secure_store import unprotect_text


def _is_routes_backup_name(name: str) -> bool:
    safe_name = posixpath.basename(str(name))
    return bool(re.match(r"^routes.*_backup_.+\.php$", safe_name, re.IGNORECASE))


def _parse_mdtm(ftp: ftplib.FTP, name: str) -> datetime:
    try:
        raw = ftp.sendcmd(f"MDTM {name}").split()[-1]
        return datetime.strptime(raw, "%Y%m%d%H%M%S")
    except Exception:
        return datetime.min


def main() -> int:
    cfg = load_config()
    host = str(cfg.get("ftp_host", "") or "").strip()
    port = int(str(cfg.get("ftp_port", "21") or "21").strip())
    user = str(cfg.get("ftp_user", "") or "").strip()
    remote_path = str(cfg.get("ftp_remote_routes_path", "") or "").strip()
    password = unprotect_text(str(cfg.get("ftp_password_dpapi", "") or ""))

    if not host or not user or not remote_path or not password:
        raise RuntimeError("FTP config incomplete")

    local_dir = Path("server")
    main_path = local_dir / "routes.php"
    local_files: list[Path] = []
    seen: set[str] = set()
    for candidate in [main_path, *sorted(local_dir.glob("routes*.php"))]:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen or not candidate.exists():
            continue
        seen.add(key)
        local_files.append(candidate)

    remote_dir = posixpath.dirname(remote_path)
    remote_main_name = posixpath.basename(remote_path)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    with ftplib.FTP() as ftp:
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        ftp.cwd(remote_dir)
        existing = set(ftp.nlst())
        uploaded: list[str] = []
        backup_names: list[str] = []

        for local_path in local_files:
            remote_name = local_path.name if local_path.name != main_path.name else remote_main_name
            stem, ext = posixpath.splitext(remote_name)
            backup_name = f"{stem}_backup_{APP_VERSION}_{stamp}{ext or '.php'}"
            if remote_name in existing:
                ftp.rename(remote_name, backup_name)
                backup_names.append(backup_name)
            with local_path.open("rb") as fh:
                ftp.storbinary(f"STOR {remote_name}", fh)
            uploaded.append(remote_name)

        backups = [name for name in ftp.nlst() if _is_routes_backup_name(name)]
        grouped: dict[str, list[str]] = {}
        for name in backups:
            base = name.split("_backup_", 1)[0]
            grouped.setdefault(base, []).append(name)

        deleted: list[str] = []
        for names in grouped.values():
            names_sorted = sorted(names, key=lambda n: _parse_mdtm(ftp, n), reverse=True)
            for name in names_sorted[3:]:
                ftp.delete(name)
                deleted.append(name)

    print("UPLOADED:", ", ".join(uploaded))
    if backup_names:
        print("BACKUPS_CREATED:", ", ".join(backup_names))
    if deleted:
        print("DELETED:", ", ".join(deleted))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
