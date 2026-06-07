from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
README = ROOT / "README.md"
STAND = ROOT / "stand.md"
HAND_BOOK = ROOT / "Handbuch.md"
ADMIN_HAND_BOOK = ROOT / "Admin-Handbuch.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def app_version() -> str:
    text = read_text(APP_DIR / "app_constants.py")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def api_version() -> str:
    text = read_text(ROOT / "server" / "routes.php")
    match = re.search(r"ODV_API_VERSION\s*=\s*'([^']+)'", text)
    return match.group(1) if match else ""


def duplicate_class_methods() -> list[str]:
    issues: list[str] = []
    for path in sorted(APP_DIR.glob("*.py")):
        try:
            tree = ast.parse(read_text(path), filename=str(path))
        except SyntaxError as exc:
            issues.append(f"{path.relative_to(ROOT)}: Syntaxfehler: {exc}")
            continue
        for class_node in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
            methods: dict[str, list[int]] = {}
            for node in class_node.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.setdefault(node.name, []).append(node.lineno)
            for name, lines in methods.items():
                if len(lines) > 1:
                    issues.append(f"{path.relative_to(ROOT)}: {class_node.name}.{name} doppelt in Zeilen {lines}")
    return issues


def version_mismatches() -> list[str]:
    issues: list[str] = []
    expected = app_version()
    if not expected:
        return ["app/app_constants.py: APP_VERSION nicht gefunden"]
    api = api_version()
    if api != expected:
        issues.append(f"server/routes.php: API-Version {api or '-'} passt nicht zu App-Version {expected}")
    docs = [
        (README, "README.md"),
        (STAND, "stand.md"),
        (HAND_BOOK, "Handbuch.md"),
        (ADMIN_HAND_BOOK, "Admin-Handbuch.md"),
    ]
    for path, label in docs:
        if not path.exists():
            issues.append(f"{label}: Datei fehlt")
            continue
        if expected not in read_text(path):
            issues.append(f"{label}: Version {expected} nicht gefunden")
    return issues


def stale_status_terms() -> list[str]:
    issues: list[str] = []
    allowed_files = {README.name}
    for path in sorted([*APP_DIR.glob("*.py"), *ROOT.glob("*.md"), *(ROOT / "server").glob("*.php")]):
        if path.name in allowed_files:
            continue
        text = read_text(path)
        if "uebernommen" in text:
            issues.append(f"{path.relative_to(ROOT)}: alter Statusbegriff 'uebernommen' gefunden")
    return issues


def large_python_modules(limit: int = 900) -> list[str]:
    issues: list[str] = []
    for path in sorted(APP_DIR.glob("*.py")):
        lines = read_text(path).splitlines()
        if len(lines) > limit:
            issues.append(f"{path.relative_to(ROOT)}: {len(lines)} Zeilen, Refactoring-Kandidat")
    return issues


def legacy_file_workflow_markers() -> list[str]:
    issues: list[str] = []
    markers = [
        "Dateien nachbearbeiten",
        "admin_tab_visible",
        "legacy_admin_table_is_active",
        "force_legacy",
    ]
    for path in sorted(APP_DIR.glob("*.py")):
        text = read_text(path)
        for marker in markers:
            if marker in text:
                issues.append(f"{path.relative_to(ROOT)}: Legacy-Marker '{marker}'")
    return issues


def main() -> int:
    checks = [
        ("Versionen", version_mismatches()),
        ("Doppelte Klassenmethoden", duplicate_class_methods()),
        ("Alte Statusbegriffe", stale_status_terms()),
        ("Große Python-Module", large_python_modules()),
        ("Legacy-Dateiworkflow", legacy_file_workflow_markers()),
    ]
    has_critical = False
    for title, issues in checks:
        print(f"\n## {title}")
        if not issues:
            print("OK")
            continue
        for issue in issues:
            print(f"- {issue}")
        if title in {"Versionen", "Doppelte Klassenmethoden", "Alte Statusbegriffe"}:
            has_critical = True
    return 1 if has_critical else 0


if __name__ == "__main__":
    sys.exit(main())
