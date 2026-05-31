from __future__ import annotations

import html
import re
import sys
import unicodedata
import webbrowser
from pathlib import Path
from tkinter import messagebox

from .config import APP_DIR


class HelpDocsMixin:
    def project_root_path(self) -> Path:
        candidates = [Path(__file__).resolve().parent.parent, Path.cwd(), Path(getattr(sys, "_MEIPASS", Path.cwd()))]
        for candidate in candidates:
            if (candidate / "Handbuch.md").exists() or (candidate / "README.md").exists():
                return candidate
        return candidates[0]

    def markdown_to_help_html(self, markdown_text: str, title: str) -> str:
        body: list[str] = []
        in_list = False
        in_table = False
        heading_counts: dict[str, int] = {}

        def slugify_heading(value: str) -> str:
            text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
            text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
            text = re.sub(r"[\s-]+", "-", text).strip("-")
            base = text or "kapitel"
            count = heading_counts.get(base, 0) + 1
            heading_counts[base] = count
            return base if count == 1 else f"{base}-{count}"

        def inline_markdown(value: str) -> str:
            result: list[str] = []
            pos = 0
            for match in re.finditer(r"\[([^\]]+)\]\((#[^)]+)\)", value):
                result.append(html.escape(value[pos:match.start()]))
                label = html.escape(match.group(1))
                href = html.escape(match.group(2), quote=True)
                result.append(f'<a href="{href}">{label}</a>')
                pos = match.end()
            result.append(html.escape(value[pos:]))
            return "".join(result)

        def close_blocks() -> None:
            nonlocal in_list, in_table
            if in_list:
                body.append("</ul>")
                in_list = False
            if in_table:
                body.append("</table>")
                in_table = False

        for raw_line in markdown_text.splitlines():
            line = raw_line.rstrip()
            if not line:
                close_blocks()
                continue
            if line.startswith("|") and line.endswith("|"):
                cells = [inline_markdown(cell.strip()) for cell in line.strip("|").split("|")]
                if all(set(cell) <= {"-", ":", " "} for cell in cells):
                    continue
                if not in_table:
                    close_blocks()
                    body.append("<table>")
                    in_table = True
                body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
                continue
            if line.startswith("#"):
                close_blocks()
                level = min(4, max(1, len(line) - len(line.lstrip("#"))))
                heading_text = line.lstrip("#").strip()
                body.append(f'<h{level} id="{slugify_heading(heading_text)}">{html.escape(heading_text)}</h{level}>')
                continue
            if line.startswith(("- ", "* ")):
                if in_table:
                    body.append("</table>")
                    in_table = False
                if not in_list:
                    body.append("<ul>")
                    in_list = True
                body.append(f"<li>{inline_markdown(line[2:].strip())}</li>")
                continue
            close_blocks()
            body.append(f"<p>{inline_markdown(line)}</p>")
        close_blocks()
        return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1100px; margin: 32px auto; padding: 0 24px; line-height: 1.55; color: #222; }}
    h1 {{ font-size: 30px; margin: 0 0 20px; }}
    h2 {{ margin-top: 32px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
    h3 {{ margin-top: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 20px; }}
    td, th {{ border: 1px solid #ccc; padding: 7px 9px; vertical-align: top; }}
    tr:nth-child(even) {{ background: #f7f7f7; }}
  </style>
</head>
<body>
{chr(10).join(body)}
</body>
</html>"""

    def open_markdown_handbook(self, filename: str, title: str) -> None:
        path = self.project_root_path() / filename
        if not path.exists():
            messagebox.showerror("Handbuch", f"Die Datei wurde nicht gefunden:\n{path}", parent=self)
            return
        try:
            markdown_text = path.read_text(encoding="utf-8")
            out_dir = APP_DIR / "help"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / (Path(filename).stem + ".html")
            out_path.write_text(self.markdown_to_help_html(markdown_text, title), encoding="utf-8", newline="\n")
            webbrowser.open(out_path.resolve().as_uri())
        except Exception as exc:
            messagebox.showerror("Handbuch", f"Das Handbuch konnte nicht geöffnet werden:\n{exc}", parent=self)
