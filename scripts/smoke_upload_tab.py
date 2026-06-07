from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import upload_tab


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class FakeCanvas:
    def __init__(self) -> None:
        self.last = None

    def delete(self, _item) -> None:
        self.last = None

    def create_oval(self, x1, y1, x2, y2, fill, outline) -> None:  # noqa: ARG002
        self.last = (x1, y1, x2, y2, fill, outline)


class FakeTk:
    @staticmethod
    def splitlist(value: str):
        # Emulates tkinter `splitlist` for the subset used in tests.
        if not value:
            return ()
        return (value.strip(),)


class FakeUploadTab(upload_tab.UploadTabMixin):
    def __init__(self, base_dir: Path) -> None:
        self.config_data = {}
        self.meta_vars = {
            "document_date": FakeVar(""),
            "event": FakeVar(""),
            "place": FakeVar(""),
            "keywords": FakeVar(""),
            "place": FakeVar(""),
            "description": FakeVar(""),
            "document_type": FakeVar(""),
            "uploaded_by": FakeVar(""),
            "status": FakeVar(""),
            "upload_id": FakeVar(""),
            "current_filename": FakeVar(""),
            "uploaded_at": FakeVar(""),
            "target_folder": FakeVar(str(base_dir)),
        }
        self.place_var = FakeVar("Roth")
        self.file_var = FakeVar("")
        self.upload_filename_var = FakeVar("")
        self.upload_drop_hint_var = FakeVar("")
        self.upload_status_canvas = FakeCanvas()
        self.upload_status_text_var = FakeVar("")
        self.upload_openai_precheck_canvas = FakeCanvas()
        self.upload_openai_precheck_var = FakeVar("")
        self.upload_openai_text_var = FakeVar("")
        self.upload_openai_usage_var = FakeVar("")
        self.upload_ocr_pdf_path = None
        self.upload_status_container = object()
        self.upload_precheck_container = object()
        self.upload_openai_metadata_button = type(
            "Btn",
            (),
            {"state": "disabled", "configure": lambda self, **_kw: None},
        )()
        self.upload_ocr_pdf_button = type(
            "Btn",
            (),
            {"grid": lambda *_a, **_k: None, "grid_remove": lambda *_a, **_k: None},
        )()
        self.upload_show_ocr_pdf_button = type(
            "Btn",
            (),
            {"grid": lambda *_a, **_k: None, "grid_remove": lambda *_a, **_k: None},
        )()
        self.upload_status_container = type(
            "Dummy",
            (),
            {"grid": lambda *_a, **_k: None, "grid_remove": lambda *_a, **_k: None},
        )()
        self.upload_precheck_container = type(
            "Dummy",
            (),
            {"grid": lambda *_a, **_k: None, "grid_remove": lambda *_a, **_k: None},
        )()
        self.target_folder_var = FakeVar(str(base_dir))
        self._upload_filename_auto_value = ""
        self.selected_file = None
        self.selected_folder = None
        self.openai_metadata_suggestions = {}
        self.openai_metadata_applied_fields = []
        self.openai_metadata_source_model = ""
        self.person_status_var = FakeVar("none")
        self.person_summary_var = FakeVar("Keine Personen markiert.")
        self.persons = []
        self.description_text = type(
            "Txt",
            (),
            {
                "get": lambda *_a, **_k: "",
                "delete": lambda *_a, **_k: None,
                "insert": lambda *_a, **_k: None,
            },
        )()
        self.note_text = type("Txt", (), {"delete": lambda *_a, **_k: None, "get": lambda *_a, **_k: ""})()
        self.upload_description_counter_var = FakeVar("")
        self.tk = FakeTk()

    def normalize_local_path_text(self, path: Path) -> str:
        return str(path)

    def refresh_upload_metadata_option_comboboxes(self) -> None:
        return None

    def remember_document_type(self, _doc_type: str) -> None:
        return None

    def apply_image_metadata_suggestions(self, _path: Path) -> None:
        return None

    def apply_filename_keyword_suggestions(self, _path: Path) -> None:
        return None

    def refresh_upload_status_ui(self) -> None:
        return None

    def update_description_counter(self, *_args, **_kwargs) -> None:
        return None


def run_smoke() -> int:
    base = Path(tempfile.mkdtemp(prefix="odv-upload-smoke-"))

    def write_valid_pdf(path: Path) -> None:
        try:
            from pypdf import PdfWriter

            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            with path.open("wb") as fh:
                writer.write_stream(fh)
            return
        except Exception:
            pass
        pdf_minimal = (
            b"%PDF-1.4\n"
            b"%\xe2\xe3\xcf\xd3\n"
            b"1 0 obj\n"
            b"<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n"
            b"2 0 obj\n"
            b"<< /Type /Pages /Kids [] /Count 0 >>\n"
            b"endobj\n"
            b"xref\n"
            b"0 3\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000079 00000 n \n"
            b"trailer\n"
            b"<< /Size 3 /Root 1 0 R >>\n"
            b"startxref\n"
            b"170\n"
            b"%%EOF\n"
        )
        path.write_bytes(pdf_minimal)

    # Dateien für Smoke
    pdf_path = base / "test.pdf"
    txt_path = base / "test.txt"
    txt_path.write_text("Dies ist ein kurzer Beispieltext für OpenAI-Vorchecks.")
    write_valid_pdf(pdf_path)

    owner = FakeUploadTab(base)

    if owner.evaluate_upload_status() != ("red", "Keine Datei"):
        print("FAIL: Upload-Status ohne Datei ist nicht rot/Keine Datei")
        return 1

    owner.selected_file = base / "fehlt.pdf"
    if owner.evaluate_upload_status()[1] != "Datei fehlt":
        print("FAIL: Upload-Status fehlt-Datei nicht erkannt")
        return 1

    owner.selected_file = txt_path
    owner.meta_vars["document_date"].set("2026-01-01")
    owner.meta_vars["event"].set("Test")
    owner.meta_vars["place"].set("Roth")
    owner.meta_vars["keywords"].set("Test")
    if owner.evaluate_upload_status() != ("green", "Bereit zum Upload"):
        print(f"FAIL: Upload-Status sollte bereit sein: {owner.evaluate_upload_status()}")
        return 1

    owner.selected_folder = base
    owner.selected_file = txt_path
    if owner.evaluate_upload_status() != ("yellow", "Ordnerupload"):
        print(f"FAIL: Ordnerupload-Status falsch: {owner.evaluate_upload_status()}")
        return 1

    # Deduplizierte Hilfszustände für OpenAI-Ampel
    owner.selected_folder = None
    color, text = owner.evaluate_openai_precheck()
    if color not in {"green", "yellow"}:
        print(f"FAIL: OpenAI-Ampel für lesbare Textdatei unerwartet: {color} / {text}")
        return 1

    # PDF ohne OCR bleibt als OCR-relevant erkannt
    owner.selected_file = pdf_path
    color, text = owner.evaluate_openai_precheck()
    if color not in {"yellow", "red"}:
        print(f"FAIL: OpenAI-Ampel für PDF-Textuntersuchung unerwartet: {color} / {text}")
        return 1

    # OCR-Pfad wird korrekt aufgelöst (erlaubt auch vorhandenes OCR-PDF)
    ocr_path = pdf_path.with_name(f"{pdf_path.stem}_ocr.pdf")
    ocr_path.write_bytes(b"%PDF-1.4")
    owner.upload_ocr_pdf_path = ocr_path
    resolved = owner.current_upload_ocr_pdf_path()
    if str(resolved) != str(ocr_path):
        print(f"FAIL: OCR-Pfadauflösung liefert {resolved}, erwartet {ocr_path}")
        return 1

    dropped = owner.parse_dropped_files("{" + str(txt_path) + "}")
    if not dropped or str(dropped[0]) != str(txt_path):
        print(f"FAIL: Drag&Drop-Parsing fehlerhaft: {dropped}")
        return 1

    print("OK: upload_tab Smoke erfolgreich")
    return 0


if __name__ == '__main__':
    raise SystemExit(run_smoke())
