from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from .config import save_config
from .file_service import load_metadata_files


class FileTreeManagerMixin:
    def on_file_view_meta_mousewheel(self, event) -> None:
        try:
            delta = int(-1 * (event.delta / 120))
        except Exception:
            try:
                delta = 120 if event.num == 4 else -120
            except Exception:
                delta = 0
        if not delta:
            return
        self.file_view_meta_canvas.yview_scroll(delta, "units")

    def clear_file_view_filter(self) -> None:
        self.file_view_filter_var.set("")
        self.refresh_file_view_tree()

    def refresh_file_view_folder_choices(self, build_tree: bool = True) -> None:
        base = self.nextcloud_base_path(show_message=False)
        self.file_view_folder_map = {}
        if base is not None and base.exists():
            candidates: list[Path] = [base]
            try:
                for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
                    if child.is_dir() and not self.is_hidden_system_path(child) and self.is_file_view_path_in_readable_branch(child, base):
                        candidates.append(child)
                        # ODV-Hauptordner unter Sammelordnern zusätzlich anbieten.
                        try:
                            for sub in sorted(child.iterdir(), key=lambda p: p.name.lower()):
                                if sub.is_dir() and not self.is_hidden_system_path(sub) and self.is_file_view_path_in_readable_branch(sub, base):
                                    candidates.append(sub)
                        except OSError:
                            pass
            except OSError:
                pass
            for folder in sorted(set(candidates), key=lambda p: str(p).lower()):
                label = self.display_path_for_folder(folder, base)
                self.file_view_folder_map[label] = folder
        values = list(self.file_view_folder_map.keys())
        self.file_view_combo["values"] = values
        current = self.file_view_root_var.get().strip()
        if values:
            if current in self.file_view_folder_map:
                self.file_view_root_var.set(current)
            else:
                selected = None
                for label, path in self.file_view_folder_map.items():
                    if str(path) == current:
                        selected = label
                        break
                self.file_view_root_var.set(selected or values[0])
            if build_tree:
                self.refresh_file_view_tree()

    def on_file_view_root_selected(self) -> None:
        self.config_data["file_view_root"] = self.file_view_root_var.get().strip()
        save_config(self.config_data)
        self.refresh_file_view_tree()

    def choose_file_view_root(self) -> None:
        folder = filedialog.askdirectory(title="Verzeichnis für Dateiansicht auswählen")
        if folder:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            path = Path(folder).expanduser()
            if self.is_odv_update_path(path):
                messagebox.showwarning("Systemordner", "Der Ordner ODV_UPDATE ist ein technischer Updateordner und kann hier nicht ausgewählt werden.")
                return
            label = self.display_path_for_folder(path, base) if base.exists() else self.normalize_local_path_text(path)
            self.file_view_folder_map[label] = path
            self.file_view_combo["values"] = list(self.file_view_folder_map.keys())
            self.file_view_root_var.set(label)
            self.on_file_view_root_selected()

    def choose_file_view_root_tree(self) -> None:
        self.refresh_file_view_folder_choices()
        folders = list(self.file_view_folder_map.values())
        selected = self.open_folder_tree_dialog("Verzeichnis für Dateiansicht auswählen", folders, self.file_view_root_var.get())
        if selected:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            label = self.display_path_for_folder(selected, base)
            self.file_view_folder_map[label] = selected
            values = list(self.file_view_combo["values"])
            if label not in values:
                values.append(label)
                values.sort(key=str.lower)
                self.file_view_combo["values"] = values
            self.file_view_root_var.set(label)
            self.on_file_view_root_selected()

    def refresh_file_view_tree(self) -> None:
        root_text = self.file_view_root_var.get().strip() or self.base_folder_var.get().strip()
        if not root_text:
            return
        root = self.file_view_folder_map.get(root_text, Path(root_text).expanduser())
        if not root.exists() or not root.is_dir():
            messagebox.showwarning("Verzeichnis", f"Verzeichnis nicht gefunden:\n{root}")
            return
        self.file_view_metadata_items = load_metadata_files(self.metadata_folder_path())
        self.file_view_metadata_by_path = {}
        for item in self.file_view_metadata_items:
            p = str(item.get("current_path", "") or "")
            if p:
                self.file_view_metadata_by_path[str(Path(p))] = item
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        root_tags = ("folder_has_files",) if self.folder_contains_files(root) else ()
        root_id = self.file_tree.insert("", "end", text=root.name or str(root), values=(str(root),), open=True, tags=root_tags)
        self._add_file_tree_children(root_id, root, depth=0)

    def current_file_view_filter_norm(self) -> str:
        return self.normalize_search_text(self.file_view_filter_var.get())

    def file_matches_current_filter(self, path: Path) -> bool:
        term = self.current_file_view_filter_norm()
        if not term:
            return True
        hay = [path.name]
        try:
            item = self.file_view_metadata_by_path.get(str(path)) or {}
            hay.extend(
                [
                    str(item.get("keywords") or ""),
                    str(item.get("description") or ""),
                    str(item.get("original_filename") or ""),
                    str(item.get("stored_filename") or ""),
                    str(item.get("current_filename") or ""),
                ]
            )
        except Exception:
            pass
        return any(term in self.normalize_search_text(x) for x in hay)

    def file_matches_current_status_filter(self, path: Path) -> bool:
        wanted = str(self.file_view_status_var.get()).strip()
        if not wanted or wanted == "alle":
            return True
        item = self.file_view_metadata_by_path.get(str(path)) or {}
        status = str(item.get("status") or "ohne").strip()
        return status == wanted

    def file_is_visible_in_current_tree(self, path: Path) -> bool:
        return (
            path.is_file()
            and not self.is_linked_ocr_file_path(path)
            and self.visible_pdf_work_file(path)
            and self.file_matches_current_filter(path)
            and self.file_matches_current_status_filter(path)
        )

    def is_linked_ocr_file_path(self, path: Path) -> bool:
        """OCR-Arbeitskopien werden über das Original geöffnet, nicht als eigenes Dokument."""
        try:
            if path.suffix.lower() != ".pdf":
                return False
            if path.stem.lower().endswith("_ocr"):
                base = path.with_name(f"{path.stem[:-4]}.pdf")
                pdfa = path.with_name(f"{path.stem[:-4]}_pdfa.pdf")
                return base.exists() or pdfa.exists()
            path_text = str(path)
            for item in self.file_view_metadata_items or []:
                ocr_text = str(item.get("ocr_pdf_path") or item.get("ocr_current_path") or "").strip()
                if ocr_text and str(Path(ocr_text)) == path_text:
                    return True
        except Exception:
            pass
        return False

    def folder_contains_files(self, folder: Path) -> bool:
        """True, wenn der Ordner selbst oder irgendein Unterordner sichtbare Dateien enthält.

        Berücksichtigt Systemdateien, Leserechte und optional den Dateinamenfilter.
        """
        base = Path(self.base_folder_var.get().strip()).expanduser()
        try:
            for child in folder.iterdir():
                if self.is_hidden_system_path(child):
                    continue
                readable_target = child if child.is_dir() else folder
                if not self.is_file_view_path_in_readable_branch(readable_target, base):
                    continue
                if self.file_is_visible_in_current_tree(child):
                    return True
                if child.is_dir() and self.folder_contains_files(child):
                    return True
        except OSError:
            return False
        return False

    def _add_file_tree_children(self, parent_id: str, folder: Path, depth: int = 0) -> None:
        try:
            children = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        base = Path(self.base_folder_var.get().strip()).expanduser()
        filter_active = bool(self.current_file_view_filter_norm())
        status_filter_active = str(self.file_view_status_var.get()).strip() != "alle"
        for child in children:
            if self.is_hidden_system_path(child):
                continue

            readable_target = child if child.is_dir() else folder
            if not self.is_file_view_path_in_readable_branch(readable_target, base):
                continue

            if child.is_dir():
                has_matching_files = self.folder_contains_files(child)
                if (filter_active or status_filter_active) and not has_matching_files:
                    continue
                tags = ("folder_has_files",) if has_matching_files else ()
                node = self.file_tree.insert(parent_id, "end", text=child.name, values=(str(child),), open=False, tags=tags)
                # v77: bewusst vollständig rekursiv einfügen, damit Bearbeiter/Admin
                # denselben Baum wie Superadmins sehen. Performance wird über
                # Systemdatei-Filter und kleinere Root-Auswahl abgefangen.
                self._add_file_tree_children(node, child, depth + 1)
            else:
                if not self.file_is_visible_in_current_tree(child):
                    continue
                display_name = child.name
                display_name = f"{self.pdf_display_prefix(child)}{display_name}"
                if str(child) not in self.file_view_metadata_by_path:
                    display_name = f"* {display_name}"
                self.file_tree.insert(parent_id, "end", text=display_name, values=(str(child),), open=False, tags=self.pdf_tree_tags(child))

    @staticmethod
    def _strip_file_tree_prefixes(text: str) -> str:
        cleaned = text
        changed = True
        while changed:
            changed = False
            for marker in ("* ", "# "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker) :]
                    changed = True
        return cleaned

    def _has_document_ocr_copy(self, path: Path, item: dict | None = None) -> bool:
        if path.suffix.lower() != ".pdf":
            return False
        if path.name.lower().endswith("_ocr.pdf"):
            return True
        linked_resolver = getattr(self, "linked_pdf_paths_for_item", None)
        if callable(linked_resolver):
            linked = linked_resolver(item, path) or {}
            if linked.get("ocr"):
                return True
        if path.with_name(f"{path.stem}_ocr.pdf").exists():
            return True
        return False

    def _format_file_tree_pdf_name(
        self,
        path: Path,
        item: dict | None,
        base_text: str,
        check_searchability: bool,
    ) -> str:
        raw_name = self._strip_file_tree_prefixes(base_text)
        raw_name = f"{self.pdf_display_prefix(path)}{raw_name}" if path.suffix.lower() == ".pdf" else raw_name
        name_has_markers = str(path) not in self.file_view_metadata_by_path
        if path.suffix.lower() != ".pdf":
            return f"* {raw_name}" if name_has_markers else raw_name

        has_ocr_copy = self._has_document_ocr_copy(path=path, item=item)
        if has_ocr_copy:
            return f"* {raw_name}" if name_has_markers else raw_name

        if check_searchability and self.pdf_is_non_searchable_text(path, has_linked_ocr=False):
            return f"* # {raw_name}" if name_has_markers else f"# {raw_name}"
        return f"* {raw_name}" if name_has_markers else raw_name

    def _update_selected_tree_item_searchability_marker(self) -> None:
        selection = self.file_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        values = self.file_tree.item(item_id, "values")
        if not values:
            return
        path = Path(values[0])
        item = self.file_view_metadata_by_path.get(str(path))
        text = str(self.file_tree.item(item_id, "text") or "")
        marked = self._format_file_tree_pdf_name(path=path, item=item, base_text=text, check_searchability=True)
        if marked and marked != text:
            self.file_tree.item(item_id, text=marked)

    def on_file_tree_select(self) -> None:
        sel = self.file_tree.selection()
        if not sel:
            return
        self._update_selected_tree_item_searchability_marker()
        values = self.file_tree.item(sel[0], "values")
        if not values:
            return
        path = Path(values[0])
        if path != self.file_view_current_path:
            self.file_preview_zoom = 1.0
        self.file_view_current_path = path
        self.file_view_current_metadata = self.file_view_metadata_by_path.get(str(path))
        self.update_file_view_preview_tab_visibility()
        self.show_file_preview()
        self.load_file_view_metadata_form()
        self.update_file_view_ocr_button()
        self.update_file_view_admin_actions_for_selection()
        self.update_admin_openai_controls()

    def open_selected_file_from_tree(self) -> None:
        """Öffnet die aktuell ausgewählte Datei mit der Standardanwendung des Betriebssystems.

        Das ist vor allem für PDF, Word, Tabellen usw. gedacht. Bilddateien können
        zusätzlich weiterhin über die Vorschau/Personenzuordnung bearbeitet werden.
        """
        sel = self.file_tree.selection()
        if not sel:
            return
        values = self.file_tree.item(sel[0], "values")
        if not values:
            return
        path = Path(values[0])
        if not path.exists() or path.is_dir():
            return
        self.open_file_with_default_app(path)


    # Admin
