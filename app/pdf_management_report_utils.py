from __future__ import annotations

from pathlib import Path
from typing import Callable

from .pdf_management_utils import build_pdf_report_row, pdf_report_csv_fieldnames


def build_pdf_report_rows(
    base: Path,
    scan_root: Path,
    is_hidden_system_path: Callable[[Path], bool],
    linked_pdf_paths_for_item: Callable[[dict | None, Path], dict[str, Path | None]],
    pdf_optimization_info_for_path: Callable[[Path], dict],
    is_non_searchable_pdf: Callable[[Path, dict[str, Path | None]], bool] | None = None,
) -> list[dict[str, str]]:
    """Erstellt die PDF-Report-Zeilen für die aktuelle Ordneransicht."""
    rows: list[dict[str, str]] = []
    seen_work: set[str] = set()
    check_non_searchable = is_non_searchable_pdf or (lambda _path, _links: False)
    for path in sorted(scan_root.rglob("*.pdf"), key=lambda p: str(p).lower()):
        if is_hidden_system_path(path):
            continue
        stem = path.stem
        if stem.lower().endswith("_ocr") or stem.lower().endswith("_pdfa"):
            work = path.with_name(f"{stem[:-4]}.pdf" if stem.lower().endswith("_ocr") else f"{stem[:-5]}.pdf")
        else:
            work = path
        key = str(work)
        if key in seen_work:
            continue
        seen_work.add(key)
        links = linked_pdf_paths_for_item(None, work)
        optimization = pdf_optimization_info_for_path(work)
        row = build_pdf_report_row(work, base, links, optimization)
        if not links.get("ocr") and check_non_searchable(work, links):
            row["name"] = f"# {row['name']}"
        rows.append(row)
    return rows


def write_pdf_size_log(rows: list[dict[str, str]], app_root: Path) -> Path:
    import csv

    log_dir = app_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    target = log_dir / "pdf_sizes.csv"
    with target.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = pdf_report_csv_fieldnames()
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target
