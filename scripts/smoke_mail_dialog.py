from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.mail_manager as mail_manager


class FakeVar:
    _all: list["FakeVar"] = []

    def __init__(self, value: str = ""):
        self._value = str(value)
        FakeVar._all.append(self)

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = str(value)

    def trace_add(self, *_args, **_kwargs) -> str:
        return "trace"


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def grid(self, *args, **kwargs):
        return self

    def pack(self, *args, **kwargs):
        return self

    def columnconfigure(self, *_args, **_kwargs):
        return None

    def rowconfigure(self, *_args, **_kwargs):
        return None

    def configure(self, *_args, **_kwargs):
        return None

    def bind(self, *_args, **_kwargs):
        return None

    def set(self, *_args, **_kwargs):
        return None

    def yview(self, *_args, **_kwargs):
        return ()

    def destroy(self, *_args, **_kwargs):
        return None

    def winfo_children(self):
        return []

    def resizable(self, *_args, **_kwargs):
        return None

    def transient(self, *_args, **_kwargs):
        return None

    def grab_set(self, *_args, **_kwargs):
        return None

    def title(self, *_args, **_kwargs):
        return None

    def geometry(self, *_args, **_kwargs):
        return None


class FakeToplevel(FakeWidget):
    pass


class FakeListbox(FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._items: list[str] = []
        self._selection: tuple[int, ...] = tuple()

    def insert(self, *_args, **_kwargs):
        value = _kwargs.get("index", None)
        if _args:
            # Tk signature: insert(index, *elements)
            elements = _args[1:]
        else:
            elements = ()
        for item in elements:
            self._items.append(str(item))
        if value == "end":
            return None
        if isinstance(value, int):
            return None

    def itemconfig(self, *_args, **_kwargs):
        return None

    def delete(self, *_args, **_kwargs):
        self._items = []
        return None

    def curselection(self):
        return self._selection

    def set_selection(self, items: tuple[int, ...]):
        self._selection = items


class FakeText(FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def insert(self, *_args):
        if len(_args) >= 2:
            self._text += str(_args[1])

    def delete(self, *_args, **_kwargs):
        self._text = ""

    def get(self, *args, **_kwargs):
        return self._text


class FakeMessageBox:
    @staticmethod
    def showerror(*_args, **_kwargs):
        return None

    @staticmethod
    def showwarning(*_args, **_kwargs):
        return None

    @staticmethod
    def showinfo(*_args, **_kwargs):
        return None

    @staticmethod
    def askyesno(*_args, **_kwargs):
        return False


class FakeFileDialog:
    @staticmethod
    def askopenfilenames(*_args, **_kwargs):
        return ()


class FakeApi:
    def me(self, _token):
        return {"user": {"username": "admin", "display_name": "Admin Nutzer", "email": "admin@ortschronik.info"}}


class FakeOwner(mail_manager.MailManagerMixin):
    def __init__(self, is_admin: bool = True) -> None:
        self._is_admin = is_admin
        self.username_var = FakeVar("admin")
        self.current_user = {"username": "admin", "display_name": "Admin Nutzer", "email": "admin@ortschronik.info"}
        self.display_name_var = FakeVar("Admin Nutzer")
        self.email_var = FakeVar("admin@ortschronik.info")
        self.base_folder_var = FakeVar("")
        self.config_data = {"current_email": "fallback@ortschronik.info"}
        self.api_token = "token"
        self.api = FakeApi()

    def load_email_users(self):
        return [
            {
                "display_name": "Admin Nutzer",
                "email": "admin@ortschronik.info",
                "username": "admin",
                "place": "Roth",
                "role": "admin",
            },
            {
                "display_name": "Mitarbeiter",
                "email": "user@ortschronik.info",
                "username": "u",
                "place": "Roth",
                "role": "user",
            },
        ]

    def load_visible_mail_groups(self):
        return []

    def is_current_admin(self):
        return bool(self._is_admin)

    def track_window_geometry(self, *_args, **_kwargs):
        return None

    def set_current_user(self, user, persist=True):
        self.current_user = user

    def make_scrolled_text(self, *args, **kwargs):
        return FakeText(), FakeWidget()

    def get_mail_text_templates(self):
        return []

    def is_path_under_nextcloud_base(self, _path: str) -> bool:
        return False

    def nextcloud_web_link_for_local_path(self, _path: str, _expires: str) -> str:
        return "https://nc.test/download"

    def normalize_mail_markup(self, value: str) -> str:
        return value

    def render_mail_html(self, value: str) -> str:
        return value

    def clipboard_clear(self):
        return None

    def clipboard_append(self, *_args, **_kwargs):
        return None

    def reset_for_case(self, *, email: str, display_name: str, username: str, config_email: str = "") -> None:
        self.current_user["username"] = username
        self.current_user["display_name"] = display_name
        self.current_user["email"] = email
        self.username_var = FakeVar(username)
        self.display_name_var = FakeVar(display_name)
        self.email_var = FakeVar(email)
        self.config_data = {"current_email": config_email}


def configure_fake_tk_modules():
    fake_tk = types.SimpleNamespace(
        Toplevel=FakeToplevel,
        StringVar=FakeVar,
        Listbox=FakeListbox,
        Label=FakeWidget,
        Frame=FakeWidget,
        Button=FakeWidget,
        Entry=FakeWidget,
        Scrollbar=FakeWidget,
        Radiobutton=FakeWidget,
        Combobox=FakeWidget,
        Text=FakeText,
    )

    fake_ttk = types.SimpleNamespace(
        Frame=FakeWidget,
        Button=FakeWidget,
        Label=FakeWidget,
        Entry=FakeWidget,
        Scrollbar=FakeWidget,
        Radiobutton=FakeWidget,
        Combobox=FakeWidget,
    )

    # Monkeypatch module globals used by the dialog.
    mail_manager.tk = fake_tk
    mail_manager.ttk = fake_ttk
    mail_manager.messagebox = FakeMessageBox()
    mail_manager.filedialog = FakeFileDialog()


def run_smoke() -> int:
    configure_fake_tk_modules()

    owner = FakeOwner()

    # Fall 1: direkte E-Mail aus current_user.
    owner.reset_for_case(email="admin@ortschronik.info", display_name="Admin Nutzer", username="admin")
    FakeVar._all = []
    owner.open_information_mail_dialog()
    direct_prefill = any(var.get() == "admin@ortschronik.info" for var in FakeVar._all)
    if not direct_prefill:
        print("FAIL: Antwort-an wurde nicht mit current_user.email vorbelegt.")
        return 1

    # Fall 2: E-Mail wird über Displayname/Benutzer aus der Benutzersammlung aufgelöst.
    owner.reset_for_case(email="", display_name="Admin Nutzer", username="admin", config_email="")
    FakeVar._all = []
    owner.open_information_mail_dialog()
    resolved_prefill = any(var.get() == "admin@ortschronik.info" for var in FakeVar._all)
    if not resolved_prefill:
        print("FAIL: Antwort-an wurde nicht über Benutzerkontext aufgelöst.")
        return 1

    # Fall 3: Fallback auf konfigurierter Standard-E-Mail, falls kein Benutzerkontext vorhanden ist.
    owner.reset_for_case(email="", display_name="Unbekannt", username="u2", config_email="fallback@ortschronik.info")
    FakeVar._all = []
    owner.open_information_mail_dialog()
    config_prefill = any(var.get() == "fallback@ortschronik.info" for var in FakeVar._all)
    if not config_prefill:
        print("FAIL: Antwort-an wurde nicht auf config current_email zurückgeführt.")
        return 1

    # Fall 4: Non-Admin-Benutzer.
    non_admin_owner = FakeOwner(is_admin=False)
    FakeVar._all = []
    non_admin_owner.open_information_mail_dialog()
    if not any("admin@ortschronik.info" == var.get() for var in FakeVar._all):
        print("FAIL: Non-admin prefill im Rundmail-Dialog fehlgeschlagen.")
        return 1

    print("OK: open_information_mail_dialog prefill scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke())
