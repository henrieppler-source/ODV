from __future__ import annotations

from pathlib import Path


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def pdf_size_mb(path: Path | None) -> float:
    try:
        if path and path.exists() and path.is_file():
            return path.stat().st_size / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def format_file_size(path: Path | None) -> str:
    mb = pdf_size_mb(path)
    if mb <= 0:
        return "-"
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def format_size_bytes(size: int | float | str | None) -> str:
    try:
        value = float(size or 0)
    except Exception:
        return "-"
    if value <= 0:
        return "-"
    mb = value / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def pdfa_path_for_document(path: Path | None) -> Path | None:
    if not path or path.suffix.lower() != ".pdf":
        return None
    if path.stem.lower().endswith("_pdfa"):
        return path
    return path.with_name(f"{path.stem}_pdfa.pdf")


def ocr_path_for_document(path: Path | None) -> Path | None:
    if not path or path.suffix.lower() != ".pdf":
        return None
    if path.stem.lower().endswith("_ocr"):
        return path
    return path.with_name(f"{path.stem}_ocr.pdf")


def is_linked_pdfa_file_path(path: Path) -> bool:
    return path.suffix.lower() == ".pdf" and path.stem.lower().endswith("_pdfa")


def pdf_display_prefix(path: Path, optimize_recommend_mb: int) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    prefix = ""
    if pdf_size_mb(path) >= optimize_recommend_mb:
        prefix += "!! "
    return prefix


def pdf_tree_tags(path: Path, optimize_recommend_mb: int) -> tuple[str, ...]:
    if path.suffix.lower() != ".pdf":
        return ()
    tags: list[str] = []
    if is_linked_pdfa_file_path(path):
        tags.append("pdfa_file")
    elif path.stem.lower().endswith("_ocr"):
        tags.append("ocr_file")
    if pdf_size_mb(path) >= optimize_recommend_mb:
        tags.append("large_pdf")
    return tuple(tags)


def visible_pdf_work_file(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return True
    if is_linked_pdfa_file_path(path):
        work = path.with_name(f"{path.stem[:-5]}.pdf")
        return not work.exists()
    return True


def pdf_report_csv_fieldnames() -> list[str]:
    return [
        "name",
        "path",
        "nextcloud_path",
        "local_available",
        "local_path",
        "folder",
        "work_size",
        "original_size",
        "optimized_by_odv",
        "pdfa_size",
        "ocr_size",
        "work_size_mb",
        "original_size_mb",
        "pdfa_size_mb",
        "ocr_size_mb",
    ]


def build_pdf_report_row(
    work: Path,
    base: Path,
    links: dict[str, Path | None],
    optimization: dict,
) -> dict[str, str]:
    work_mb = pdf_size_mb(links.get("work"))
    pdfa_mb = pdf_size_mb(links.get("pdfa"))
    ocr_mb = pdf_size_mb(links.get("ocr"))
    relative_path = str(work.relative_to(base)) if work.is_relative_to(base) else work.name
    nextcloud_path = relative_path.replace("\\", "/")
    original_size = optimization.get("original_size")
    return {
        "name": work.name,
        "path": str(work),
        "local_path": str(work),
        "nextcloud_path": nextcloud_path,
        "local_available": "ja",
        "folder": str(work.parent.relative_to(base)) if work.parent != base else "",
        "work_size_mb": f"{work_mb:.3f}",
        "original_size_mb": f"{(float(original_size) / (1024 * 1024)):.3f}" if original_size else "",
        "pdfa_size_mb": f"{pdfa_mb:.3f}" if pdfa_mb else "",
        "ocr_size_mb": f"{ocr_mb:.3f}" if ocr_mb else "",
        "work_size": format_file_size(links.get("work")),
        "original_size": format_size_bytes(original_size),
        "optimized_by_odv": "ja" if optimization.get("result") == "optimized" else ("X" if optimization else "nein"),
        "pdfa_size": format_file_size(links.get("pdfa")),
        "ocr_size": format_file_size(links.get("ocr")),
    }
