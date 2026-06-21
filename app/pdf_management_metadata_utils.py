from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import APP_DIR
from .file_service import load_metadata_files
from .pdf_management_report_utils import build_pdf_report_rows as _pmm_build_pdf_report_rows
from .pdf_management_report_utils import write_pdf_size_log as _pmm_write_pdf_size_log


def pdf_optimization_info_for_path(manager: Any, path: Path | None) -> dict:
    if not path:
        return {}
    item = manager.item_for_local_path(path) or {}
    optimized_at = str(item.get("pdf_optimized_at") or "").strip()
    attempted_at = str(item.get("pdf_optimization_attempted_at") or "").strip()
    if not optimized_at and not attempted_at:
        return {}
    optimized_by = str(item.get("pdf_optimized_by") or item.get("edited_by") or item.get("uploaded_by") or "ODV").strip()
    return {
        "optimized_at": optimized_at,
        "attempted_at": attempted_at,
        "optimized_by": optimized_by,
        "original_size": item.get("pdf_original_size_bytes") or "",
        "optimized_size": item.get("pdf_optimized_size_bytes") or "",
        "tool": str(item.get("pdf_optimization_tool") or "").strip(),
        "profile": str(item.get("pdf_optimization_profile") or "").strip(),
        "result": str(item.get("pdf_optimization_result") or ("optimized" if optimized_at else "no_gain")).strip(),
    }


def linked_pdf_paths_for_item(manager: Any, item: dict | None, document_path: Path | None = None) -> dict[str, Path | None]:
    path = document_path or manager.resolve_document_local_path(item or {})
    ocr_path = None
    if item:
        ocr_text = str(item.get("ocr_pdf_path") or item.get("ocr_current_path") or "").strip()
        if ocr_text:
            candidate = Path(ocr_text)
            if candidate.exists():
                ocr_path = candidate
    if not ocr_path:
        ocr_candidate = manager.ocr_path_for_document(path)
        if ocr_candidate and ocr_candidate.exists():
            ocr_path = ocr_candidate
    pdfa_path = None
    pdfa_candidate = manager.pdfa_path_for_document(path)
    if pdfa_candidate and pdfa_candidate.exists():
        pdfa_path = pdfa_candidate
    return {"work": path, "pdfa": pdfa_path, "ocr": ocr_path}


def ensure_pdf_metadata_item(manager: Any, source: Path) -> tuple[dict, Path]:
    item, metadata_file = manager.ensure_file_view_metadata_item(source)
    manager.file_view_metadata_by_path[str(source)] = item
    return item, metadata_file


def refresh_pdf_views_after_action(manager: Any) -> None:
    try:
        manager.refresh_file_view_tree()
    except Exception:
        pass


def pdf_report_rows(manager: Any, root: Path | None = None) -> list[dict[str, str]]:
    base = Path(str(manager.base_folder_var.get() or ""))
    scan_root = root or base
    if not base.exists() or not base.is_dir():
        return []
    if not scan_root.exists() or not scan_root.is_dir():
        return []
    if not manager.file_view_metadata_by_path:
        try:
            manager.file_view_metadata_items = load_metadata_files(manager.metadata_folder_path())
            manager.file_view_metadata_by_path = {
                str(Path(str(item.get("current_path") or ""))): item
                for item in manager.file_view_metadata_items
                if str(item.get("current_path") or "").strip()
            }
        except Exception:
            pass
    return _pmm_build_pdf_report_rows(
        base,
        scan_root,
        manager.is_hidden_system_path,
        manager.linked_pdf_paths_for_item,
        manager.pdf_optimization_info_for_path,
        lambda path, links: manager.pdf_is_non_searchable_text(path, has_linked_ocr=bool(links.get("ocr"))),
    )


def write_pdf_size_log(manager: Any, rows: list[dict[str, str]] | None = None) -> Path:
    rows = rows if rows is not None else manager.pdf_report_rows()
    return _pmm_write_pdf_size_log(rows, APP_DIR)
