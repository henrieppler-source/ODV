from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .pdf_management_utils import dedupe_paths as _pmm_dedupe_paths


def build_pdf_tool_search_roots(
    app_dir: Path,
    module_file: Path,
    executable: str | Path | None = None,
    cwd: Path | None = None,
    meipass_root: Path | None = None,
) -> list[Path]:
    roots: list[Path] = []
    if executable:
        try:
            roots.append(Path(executable).resolve().parent)
        except Exception:
            pass
    if meipass_root:
        roots.append(meipass_root)
    roots.extend(
        [
            app_dir,
            module_file.resolve().parent.parent,
            cwd or Path.cwd(),
        ]
    )
    return _pmm_dedupe_paths(roots)


def ghostscript_executable_candidates(roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        for base in (
            root / "tools" / "ghostscript",
            root / "ghostscript",
        ):
            candidates.extend(
                [
                    base / "bin" / "gswin64c.exe",
                    base / "bin" / "gswin32c.exe",
                    base / "bin" / "gs.exe",
                ]
            )
            try:
                candidates.extend(sorted(base.glob("gs*/bin/gswin64c.exe"), reverse=True))
                candidates.extend(sorted(base.glob("gs*/bin/gswin32c.exe"), reverse=True))
            except Exception:
                pass
    return _pmm_dedupe_paths(candidates)


def ghostscript_installer_candidates(roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        installer_dir = root / "tools" / "ghostscript_installer"
        try:
            candidates.extend(sorted(installer_dir.glob("*.msi"), reverse=True))
            candidates.extend(sorted(installer_dir.glob("*.exe"), reverse=True))
        except Exception:
            pass
    return _pmm_dedupe_paths(candidates)


def find_ghostscript_command(roots: list[Path]) -> list[str] | None:
    for exe in ghostscript_executable_candidates(roots):
        if exe.exists() and exe.is_file():
            return [str(exe)]

    for name in ("gswin64c.exe", "gswin32c.exe", "gs"):
        executable = shutil.which(name)
        if executable:
            return [executable]

    candidates = [
        Path("C:/Program Files/gs"),
        Path("C:/Program Files (x86)/gs"),
    ]
    for root in candidates:
        if not root.exists():
            continue
        for exe in sorted(root.glob("gs*/bin/gswin64c.exe"), reverse=True):
            return [str(exe)]
        for exe in sorted(root.glob("gs*/bin/gswin32c.exe"), reverse=True):
            return [str(exe)]
    return None


def find_bundled_ghostscript_installer(roots: list[Path]) -> Path | None:
    for installer in ghostscript_installer_candidates(roots):
        if installer.exists() and installer.is_file():
            return installer
    return None


def install_bundled_ghostscript(installer: Path, app_dir: Path) -> None:
    suffix = installer.suffix.lower()
    if suffix == ".msi":
        cmd = ["msiexec.exe", "/i", str(installer), "/quiet", "/norestart"]
    elif suffix == ".exe":
        target_dir = app_dir / "tools" / "ghostscript"
        target_dir.mkdir(parents=True, exist_ok=True)
        cmd = [str(installer), "/S", f"/D={target_dir}"]
    else:
        raise RuntimeError(f"Nicht unterstützter Ghostscript-Installer: {installer}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or f"Exitcode {result.returncode}").strip()
        raise RuntimeError(message[:1600])


def run_ghostscript_installer_elevated(installer: Path, app_dir: Path) -> bool:
    if os.name != "nt":
        return False
    suffix = installer.suffix.lower()
    if suffix == ".msi":
        args = f'/i "{installer}" /quiet /norestart'
        os.startfile("msiexec.exe", "runas", args)  # type: ignore[attr-defined]
        return True
    if suffix == ".exe":
        target_dir = app_dir / "tools" / "ghostscript"
        target_dir.mkdir(parents=True, exist_ok=True)
        args = f'/S /D={target_dir}'
        os.startfile(str(installer), "runas", args)  # type: ignore[attr-defined]
        return True
    return False
