from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main_window_mixin import MainWindowMixin  # noqa: E402


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class FakeMenu:
    def __init__(self, *_args, **_kwargs) -> None:
        self.label = ""
        self.children: list[dict[str, object]] = []
        self._postcommand = None

    def add_cascade(self, label: str, menu) -> None:
        self.children.append({"type": "cascade", "label": label, "menu": menu})

    def add_command(self, **kwargs) -> None:
        self.children.append(
            {"type": "command", "label": kwargs.get("label", ""), "command": kwargs.get("command")}
        )

    def add_separator(self) -> None:
        self.children.append({"type": "separator"})

    def child_labels(self) -> list[str]:
        return [entry.get("label", "") for entry in self.children if isinstance(entry, dict) and "label" in entry]

    def child_labels_by_type(self, entry_type: str) -> list[str]:
        return [
            entry.get("label", "")
            for entry in self.children
            if isinstance(entry, dict)
            and entry.get("type") == entry_type
            and "label" in entry
        ]

    def entrycget(self, _index, _option=None):  # pragma: no cover - test shim only
        if isinstance(_index, int) and 0 <= _index < len(self.children):
            item = self.children[_index]
            if isinstance(item, dict):
                return item.get("label", "")
        return ""

    def config(self, **_kwargs) -> None:
        return None

    def delete(self, *_args, **_kwargs) -> None:
        # Minimal emulation used by post-command cleanup checks.
        if len(_args) == 1:
            idx = _args[0]
        elif len(_args) >= 2:
            idx = _args[0]
        else:
            return None

        if idx == "end":
            idx = len(self.children) - 1
        if isinstance(idx, str):
            try:
                idx = int(idx)
            except ValueError:
                return None
        if isinstance(idx, int) and 0 <= idx < len(self.children):
            del self.children[idx]
        return None

    def insert_command(self, index, label: str, command=None, **_kwargs) -> None:
        entry = {"type": "command", "label": label, "command": command}
        if index in {"end", None}:
            self.children.append(entry)
            return
        if isinstance(index, int):
            if index < 0:
                index = max(0, len(self.children) + index)
            if index >= len(self.children):
                self.children.append(entry)
            else:
                self.children.insert(index, entry)
            return
        self.children.append(entry)

    def index(self, _name) -> int | None:
        return len(self.children) - 1

    def configure(self, **kwargs) -> None:
        if "postcommand" in kwargs:
            self._postcommand = kwargs["postcommand"]
        return None

    def invoke_postcommand(self) -> None:
        if callable(self._postcommand):
            self._postcommand()


def get_menu_by_label(menu: FakeMenu, label: str) -> FakeMenu | None:
    for entry in menu.children:
        if (
            isinstance(entry, dict)
            and entry.get("label") == label
            and isinstance(entry.get("menu"), FakeMenu)
        ):
            return entry.get("menu")
    return None


def menu_command_labels(menu: FakeMenu) -> list[str]:
    return [
        entry.get("label", "")
        for entry in menu.children
        if isinstance(entry, dict) and entry.get("type") == "command"
    ]


class FakeStyle:
    def theme_use(self, *_args, **_kwargs):
        return None

    def configure(self, *_args, **_kwargs):
        return None

    def map(self, *_args, **_kwargs):
        return None


class FakeNotebook:
    def __init__(self, *_args, **_kwargs) -> None:
        self.tabs_added: list[tuple[object, str]] = []
        self._selected = ""

    def grid(self, *_args, **_kwargs):
        return None

    def add(self, frame, text: str) -> None:
        self.tabs_added.append((frame, text))
        if not self._selected:
            self._selected = text

    def bind(self, *_args, **_kwargs):
        return None

    def select(self) -> str:
        return self._selected

    def tabs(self):
        return [str(i) for i in range(len(self.tabs_added))]

    def tab(self, _tab_id, **_kwargs):
        return None


class FakeFrame:
    def __init__(self, *_args, **_kwargs) -> None:
        self._children: list[object] = []

    def grid(self, *_args, **_kwargs):
        return None

    def columnconfigure(self, *_args, **_kwargs):
        return None

    def rowconfigure(self, *_args, **_kwargs):
        return None


class FakeLabel:
    def __init__(self, *_args, **_kwargs) -> None:
        return None

    def grid(self, *_args, **_kwargs):
        return None


class FakeToplevel:
    def __init__(self, *_args, **_kwargs) -> None:
        self.destroyed = False

    def overrideredirect(self, *_args, **_kwargs):
        return None

    def configure(self, *_args, **_kwargs):
        return None

    def attributes(self, *_args, **_kwargs):
        return None

    def update_idletasks(self):
        return None

    def winfo_screenwidth(self):
        return 1024

    def winfo_screenheight(self):
        return 768

    def geometry(self, *_args, **_kwargs):
        return None

    def update(self):
        return None

    def after(self, *_args, **_kwargs):
        return None

    def wait_window(self):
        self.destroyed = True


class FakeWidgetMixin:
    def __init__(self, *_args, **_kwargs):
        self.kwargs = _kwargs

    def pack(self, *_args, **_kwargs):
        return None

    def grid(self, *_args, **_kwargs):
        return None

    def columnconfigure(self, *_args, **_kwargs):
        return None

    def rowconfigure(self, *_args, **_kwargs):
        return None


class FakeTTK:
    class Menu(FakeMenu):
        pass

    Frame = FakeFrame
    Notebook = FakeNotebook
    Label = FakeLabel
    Style = FakeStyle

    @staticmethod
    def Combobox(*_args, **_kwargs):
        return FakeWidgetMixin()

    @staticmethod
    def Entry(*_args, **_kwargs):
        return FakeWidgetMixin()

    @staticmethod
    def Scrollbar(*_args, **_kwargs):
        return FakeWidgetMixin()

    @staticmethod
    def Button(*_args, **_kwargs):
        return FakeWidgetMixin()

    @staticmethod
    def Checkbutton(*_args, **_kwargs):
        return FakeWidgetMixin()


class FakeTK:
    Menu = FakeMenu
    Frame = FakeFrame
    Label = FakeLabel

    class StringVar:
        def __init__(self, value: str = ""):
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    Toplevel = FakeToplevel
    class TclError(Exception):
        pass

    def __getattr__(self, name):
        raise AttributeError(name)


class FakeAPI:
    def status(self):
        return {"api_version": "v1", "maintenance": {}}


def configure_fake_tk() -> None:
    import app.main_window_mixin as mw

    class MessageBoxShim:
        @staticmethod
        def showinfo(*_a, **_k):
            return None

    mw.tk = FakeTK()
    mw.ttk = FakeTTK()
    mw.messagebox = MessageBoxShim()


class MainWindowSmokeOwner(MainWindowMixin):
    def __init__(self, role: str = "Admin") -> None:
        self.role = role
        self.base_folder_var = FakeVar(str(Path(__file__).resolve().parent.parent / "tmp_base"))
        self.api = FakeAPI()
        self.api_status_var = FakeVar()
        self.nextcloud_status_var = FakeVar()
        self.notebook: FakeNotebook | None = None
        self.admin_tab = None
        self.upload_tab = None
        self.history_tab = None
        self.viewer_tab = None
        self.config_calls = []
        self.menubar = None

    def columnconfigure(self, *_args, **_kwargs):
        return None

    def rowconfigure(self, *_args, **_kwargs):
        return None

    def create_styles(self):
        return None

    def make_scrollable_tab(self, container):
        return container

    def create_history_tab(self):
        return None

    def create_upload_tab(self):
        return None

    def create_admin_tab(self):
        return None

    def create_file_view_tab(self):
        return None

    def ensure_standard_metadata_folder(self):
        return None

    def apply_selected_user(self):
        return None

    def update_tab_labels(self):
        return None

    def update_connection_status(self):
        self.api_status_var.set("API: verbunden")
        self.nextcloud_status_var.set("Nextcloud: ok")

    def bind_global_mousewheel(self):
        return None

    def open_markdown_handbook(self, *_args, **_kwargs):
        return None

    def open_masterdata_dialog(self):
        return None

    def load_writable_folders(self):
        return None

    def logout_and_login(self):
        return None

    def open_admin_settings_dialog(self):
        return None

    def open_filename_normalization_dialog(self):
        return None

    def open_operating_mode_dialog(self):
        return None

    def open_user_management_dialog(self):
        return None

    def open_place_folder_dialog(self):
        return None

    def open_archive_collection_dialog(self):
        return None

    def open_import_existing_files_dialog(self):
        return None

    def open_local_backup_cleanup_dialog(self):
        return None

    def open_standard_mail_texts_dialog(self):
        return None

    def open_maintenance_dialog(self):
        return None

    def open_database_migrations_dialog(self):
        return None

    def open_database_reset_dialog(self):
        return None

    def open_database_backup_dialog(self):
        return None

    def open_database_restore_dialog(self):
        return None

    def open_routes_deploy_dialog(self):
        return None

    def open_app_update_admin_dialog(self):
        return None

    def open_mail_group_management_dialog(self):
        return None

    def open_mail_history_dialog(self):
        return None

    def open_my_points_dialog(self):
        return None

    def open_points_summary_dialog(self):
        return None

    def open_manual_points_dialog(self):
        return None

    def open_manual_special_points_dialog(self):
        return None

    def open_manual_special_points_overview_dialog(self):
        return None

    def open_point_rules_dialog(self):
        return None

    def open_sessions_devices_dialog(self):
        return None

    def open_pdf_overview_dialog(self):
        return None

    def open_backup_status_dialog(self):
        return None

    def open_document_access_log_dialog(self):
        return None

    def open_system_status_dialog(self):
        return None

    def open_log_folder(self):
        return None

    def check_app_update(self, *_args, **_kwargs):
        return None

    def recalculate_points_for_visible_admin_uploads(self):
        return None

    def open_points_settings_dialog(self):
        return None

    def open_information_mail_dialog(self):
        return None

    def current_role(self) -> str:
        return self.role

    def is_current_admin(self) -> bool:
        return self.role in {"Admin", "Superadmin"}

    def report_current_device_version(self):
        return None

    def on_notebook_tab_changed(self, *_args, **_kwargs):
        return None

    def config(self, **kwargs):
        self.config_calls.append(kwargs)
        if "menu" in kwargs:
            self.menubar = kwargs["menu"]

    def destroy(self) -> None:
        return None


def run_smoke(role: str) -> int:
    configure_fake_tk()
    owner = MainWindowSmokeOwner(role=role)
    owner.create_ui()

    if owner.notebook is None:
        print(f"FAIL[{role}]: Notebook wurde nicht gesetzt.")
        return 1
    if len(owner.notebook.tabs_added) < 3:
        print(f"FAIL[{role}]: Unerwartete Tabanzahl: {len(owner.notebook.tabs_added)}")
        return 1

    labels = [label for (_, label) in owner.notebook.tabs_added]
    expected = {"Dashboard", "Dateien hochladen", "Dateien anzeigen/bearbeiten"}
    missing = [label for label in expected if label not in labels]
    if missing:
        print(f"FAIL[{role}]: Fehlende Tabs: {missing}")
        return 1

    if not owner.config_calls:
        print(f"FAIL[{role}]: config() wurde nicht aufgerufen.")
        return 1

    if owner.menubar is None:
        print(f"FAIL[{role}]: Menü wurde nicht gebunden.")
        return 1

    top_labels = owner.menubar.child_labels()
    required = {"Datei", "Punkte", "Mail", "Hilfe"}
    missing = [label for label in required if label not in top_labels]
    if missing:
        print(f"FAIL[{role}]: Fehlende Menüs: {missing}")
        return 1

    if role == "User":
        if "Admin" in top_labels:
            print(f"FAIL[{role}]: Unerwartetes Admin-Menü für Nicht-Admin.")
            return 1
        if "Übersichten" in top_labels:
            print(f"FAIL[{role}]: Unerwartetes Übersichten-Menü für Nicht-Admin.")
            return 1
    else:
        if role == "Superadmin" and "Admin" not in top_labels:
            print(f"FAIL[{role}]: Admin-Menü fehlt.")
            return 1
        if "Übersichten" not in top_labels:
            print(f"FAIL[{role}]: Übersichten-Menü fehlt.")
            return 1

    if role in {"Admin", "Superadmin"}:
        points_menu = get_menu_by_label(owner.menubar, "Punkte")
        if points_menu is None:
            print(f"FAIL[{role}]: Punkte-Menü nicht im menubar gefunden.")
            return 1
        doc_item_label = "Sonderpunkte zum ausgewählten Dokument..."
        if owner.viewer_tab is None:
            print(f"FAIL[{role}]: viewer_tab fehlt für Punkte-Postcommand-Test.")
            return 1
        owner.notebook._selected = str(owner.viewer_tab)
        points_menu.invoke_postcommand()
        labels = menu_command_labels(points_menu)
        if doc_item_label not in labels:
            print(
                f"FAIL[{role}]: Dokument-Punkte-Eintrag wurde bei "
                "aktiver Viewer-Ansicht nicht eingebunden."
            )
            return 1
        points_menu.invoke_postcommand()
        labels = menu_command_labels(points_menu)
        if labels.count(doc_item_label) != 1:
            print(
                f"FAIL[{role}]: Dokument-Punkte-Eintrag wurde mehrfach "
                f"eingebunden ({labels.count(doc_item_label)}x)."
            )
            return 1
        if owner.history_tab is None:
            print(f"FAIL[{role}]: history_tab fehlt für Punkte-Postcommand-Test.")
            return 1
        owner.notebook._selected = str(owner.history_tab)
        points_menu.invoke_postcommand()
        labels = menu_command_labels(points_menu)
        if doc_item_label in labels:
            print(f"FAIL[{role}]: Dokument-Punkte-Eintrag wurde bei nicht aktivem Viewer nicht entfernt.")
            return 1

    print(f"OK[{role}]: MainWindow create_ui-Kernpfad abgeschlossen.")
    return 0


def main() -> int:
    for role in ("User", "Admin", "Superadmin"):
        if run_smoke(role):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
