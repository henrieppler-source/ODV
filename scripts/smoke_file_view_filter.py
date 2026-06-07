from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import file_tree_manager as ftm  # noqa: E402


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = str(value)


class FakeCombo:
    def __init__(self) -> None:
        self.values: list[str] = []

    def __setitem__(self, key, value):
        if key == "values":
            self.values = list(value)

    def __getitem__(self, key):
        if key == "values":
            return self.values
        raise KeyError(key)


class FakeTree:
    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._next = 0

    def _new_id(self) -> str:
        self._next += 1
        return f"n{self._next}"

    def insert(self, parent, _index, **kwargs):
        node_id = self._new_id()
        self._nodes[node_id] = {
            "parent": parent,
            "kwargs": kwargs,
            "children": [],
        }
        if parent in self._nodes:
            self._nodes[parent]["children"].append(node_id)
        return node_id

    def get_children(self, node: str | None = None):
        if node is None or node == "":
            return tuple(i for i, d in self._nodes.items() if d["parent"] == "")
        return tuple(self._nodes.get(node, {}).get("children", ()))

    def delete(self, item) -> None:
        if isinstance(item, str) and item in self._nodes:
            for child in list(self._nodes[item]["children"]):
                self.delete(child)
            self._nodes.pop(item, None)
        elif isinstance(item, (list, tuple)):
            for entry in item:
                self.delete(entry)

    def item(self, node_id, key=None):
        entry = self._nodes[node_id]["kwargs"]
        if key is None:
            return entry
        if key == "values":
            return tuple(entry.get("values", ()))
        if key == "text":
            return entry.get("text")
        return entry.get(key)

    def walk_values(self) -> list[str]:
        values: list[str] = []
        for node_id, data in self._nodes.items():
            if data.get("children"):
                continue
            node_values = data.get("kwargs", {}).get("values", ())
            if node_values:
                text = str(node_values[0])
                if text.endswith(".pdf"):
                    values.append(text)
        return values


class FileViewSmokeOwner(ftm.FileTreeManagerMixin):
    def __init__(self, base: Path, metadata_items: list[dict]) -> None:
        self.base_folder_var = FakeVar(str(base))
        self.file_view_root_var = FakeVar("")
        self.file_view_filter_var = FakeVar("")
        self.file_view_status_var = FakeVar("alle")
        self.file_view_folder_map: dict[str, Path] = {}
        self.file_view_combo = FakeCombo()
        self.file_tree = FakeTree()
        self.file_view_metadata_items = metadata_items
        self.file_view_metadata_by_path = {}
        self.config_data: dict[str, str] = {}
        self.file_view_meta_canvas = type(
            "C",
            (),
            {"yview_scroll": lambda *_args, **_kwargs: None},
        )()

    def nextcloud_base_path(self, show_message: bool = False):
        return Path(self.base_folder_var.get())

    def metadata_folder_path(self):
        return Path(self.base_folder_var.get()) / "__metadata__"

    def is_hidden_system_path(self, path: Path) -> bool:
        if path.name.startswith("."):
            return True
        return False

    def is_file_view_path_in_readable_branch(self, _path: Path, _base: Path) -> bool:
        return True

    def display_path_for_folder(self, folder: Path, _base: Path) -> str:
        try:
            return str(folder.relative_to(_base))
        except Exception:
            return str(folder)

    def normalize_local_path_text(self, path: Path) -> str:
        return str(path)

    def normalize_search_text(self, value: str) -> str:
        return (value or "").strip().lower()

    def visible_pdf_work_file(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def pdf_display_prefix(self, _path: Path) -> str:
        return ""

    def pdf_tree_tags(self, _path: Path):
        return ()

    def open_folder_tree_dialog(self, *_args, **_kwargs):
        return None

    def is_odv_update_path(self, _path: Path) -> bool:
        return _path.name.upper() == "ODV_UPDATE"

    def on_file_view_root_selected(self) -> None:
        self.config_data["file_view_root"] = self.file_view_root_var.get().strip()
        ftm.save_config(self.config_data)
        self.refresh_file_view_tree()

    def update_file_view_preview_tab_visibility(self):  # noqa: D401
        return None

    def show_file_preview(self):
        return None

    def load_file_view_metadata_form(self):
        return None

    def update_file_view_ocr_button(self):
        return None

    def update_file_view_admin_actions_for_selection(self):
        return None

    def update_admin_openai_controls(self):
        return None


def setup_fixture() -> tuple[Path, list[dict], Path]:
    base = Path(tempfile.mkdtemp(prefix="odv-smoke-"))
    (base / "00_ORTSCHRONIK" / "01").mkdir(parents=True, exist_ok=True)
    (base / "01_ABLAGE_ORTSCHRONIK").mkdir(parents=True, exist_ok=True)
    (base / ".hidden").mkdir(parents=True, exist_ok=True)
    (base / "ODV_UPDATE").mkdir(parents=True, exist_ok=True)

    file_erfasst = base / "00_ORTSCHRONIK" / "01" / "alpha_erfasst.pdf"
    file_ohne = base / "01_ABLAGE_ORTSCHRONIK" / "beta_ohne.pdf"
    file_anderes = base / "01_ABLAGE_ORTSCHRONIK" / "gamma_anderes.txt"
    file_erfasst.write_bytes(b"%PDF-1.4")
    file_ohne.write_bytes(b"%PDF-1.4")
    file_anderes.write_text("text")

    metadata = [
        {"current_path": str(file_erfasst), "status": "erfasst"},
        {"current_path": str(file_ohne), "status": "ohne"},
    ]
    return base, metadata, file_erfasst


def run_smoke() -> int:
    base, metadata, pdf_erfasst = setup_fixture()
    owner = FileViewSmokeOwner(base, metadata)

    # Fake load_metadata_files for refresh_file_view_tree
    ftm.load_metadata_files = lambda *_args, **_kwargs: metadata
    # no-op config writer
    ftm.save_config = lambda *_args, **_kwargs: None

    try:
        owner.refresh_file_view_folder_choices()
        if not owner.file_view_combo.values:
            print("FAIL: Keine Ordnerwerte in Dateiansicht.")
            return 1
        if len(owner.file_view_combo.values) < 3:
            print(f"FAIL: Erwartet mind. 3 Ordner-Kandidaten, erhalten: {owner.file_view_combo.values}")
            return 1

        first = owner.file_view_combo.values[0]
        owner.file_view_root_var.set(first)
        owner.refresh_file_view_tree()
        root_nodes = owner.file_tree.get_children("")
        if not root_nodes:
            print("FAIL: Kein Root-Knoten im Baum aufgebaut.")
            return 1

        owner.file_view_filter_var.set("alpha")
        owner.file_view_status_var.set("erfasst")
        owner.refresh_file_view_tree()
        listed = owner.file_tree.walk_values()
        if str(pdf_erfasst) not in listed:
            print(f"FAIL: Erwartete Datei nicht im gefilterten Baum: {str(pdf_erfasst)}")
            return 1
        if len(listed) != 1:
            print(f"FAIL: Unerwartete Trefferzahl bei Filter/Status: {listed}")
            return 1

        owner.file_view_filter_var.set("")
        owner.file_view_status_var.set("alle")
        owner.refresh_file_view_tree()
        all_items = owner.file_tree.walk_values()
        if len(all_items) < 2:
            print(f"FAIL: Erwartet mindestens 2 sichtbare Dateien bei Status=alle, erhalten: {all_items}")
            return 1

        # Dateifilter auf nicht vorhandenes Kriterium -> keine Treffer
        owner.file_view_filter_var.set("nichtvorhanden")
        owner.refresh_file_view_tree()
        if owner.file_tree.walk_values():
            print(
                "FAIL: Filter 'nichtvorhanden' sollte keine Dateien anzeigen, "
                f"hatte: {owner.file_tree.walk_values()}"
            )
            return 1

        print("OK: Dateiansicht-Ordnerfilter/Statusfilter Smoke erfolgreich.")
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run_smoke())
