from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .app_logging import app_log
from .config import save_config
from .file_service import find_writable_folders


class ConfigFoldersMixin:
    # Konfiguration / Ordner
    def save_basic_config(self, show_message: bool = True) -> None:
        # Name, Benutzername, Rolle und Ort kommen aus der Benutzerverwaltung.
        # Hier speichern wir nur lokale Stammdaten wie Nextcloud-Stammverzeichnis.
        self.config_data["display_name"] = self.display_name_var.get().strip() or "Ortschronist/in"
        self.config_data["current_username"] = self.username_var.get().strip()
        self.config_data["current_role"] = self.role_var.get().strip() or "Ortschronist"
        self.config_data["current_place"] = self.place_var.get().strip()
        self.config_data["nextcloud_base_folder"] = self.normalize_local_path_text(self.base_folder_var.get().strip())
        self.base_folder_var.set(self.config_data["nextcloud_base_folder"])
        self.ensure_standard_metadata_folder()
        self.config_data["metadata_folder"] = self.metadata_folder_var.get().strip()
        save_config(self.config_data)
        self.apply_selected_user()
        if show_message:
            messagebox.showinfo("Gespeichert", "Stammdaten wurden gespeichert.")

    def choose_base_folder(self, parent: tk.Toplevel | None = None) -> None:
        folder = filedialog.askdirectory(title="Nextcloud-Stammverzeichnis auswählen", parent=parent or self)
        if folder:
            self.base_folder_var.set(self.normalize_local_path_text(folder))
            self.ensure_standard_metadata_folder()
            self.save_basic_config(show_message=False)
            self.load_writable_folders()

    def choose_metadata_folder(self) -> None:
        folder = filedialog.askdirectory(title="Zentralen Metadaten-Ordner auswählen")
        if folder:
            self.metadata_folder_var.set(self.normalize_local_path_text(folder))
            self.save_basic_config()


    def ensure_standard_metadata_folder(self) -> None:
        if not hasattr(self, "metadata_folder_var") or not hasattr(self, "base_folder_var"):
            return
        base_text = self.base_folder_var.get().strip()
        if not base_text:
            self.metadata_folder_var.set("")
            self.config_data["metadata_folder"] = ""
            return
        folder_name = self.config_data.get("metadata_folder_name", ".ortschronik_metadaten") or ".ortschronik_metadaten"
        folder_name = str(folder_name).strip().replace("/", "_").replace("\\", "_")
        if not folder_name.startswith("."):
            folder_name = "." + folder_name
        self.config_data["metadata_folder_name"] = folder_name
        default_folder = Path(base_text).expanduser() / folder_name
        self.metadata_folder_var.set(self.normalize_local_path_text(default_folder))
        self.config_data["metadata_folder"] = self.normalize_local_path_text(default_folder)

    def set_default_metadata_folder(self, show_message: bool = True) -> None:
        base = Path(self.base_folder_var.get().strip()).expanduser()
        if not str(base).strip():
            messagebox.showwarning("Kein Basisordner", "Bitte zuerst den Nextcloud-Basisordner auswählen.")
            return
        self.ensure_standard_metadata_folder()
        default_folder = Path(self.metadata_folder_var.get().strip())
        save_config(self.config_data)
        if show_message:
            messagebox.showinfo("Metadaten-Ordner", f"Standard-Metadatenordner gesetzt:\n{default_folder}")

    def nextcloud_base_path(self, show_message: bool = False) -> Path | None:
        """Liefert das konfigurierte lokale Nextcloud-Stammverzeichnis.

        Wichtig für PyInstaller/EXE: Ein leerer Pfad darf niemals als aktueller
        Programmordner interpretiert werden, sonst erscheinen _internal, PIL,
        pypdf usw. in der Zielordnerauswahl.
        """
        base_text = self.base_folder_var.get().strip() if hasattr(self, "base_folder_var") else ""
        if not base_text:
            if show_message:
                messagebox.showwarning("Nextcloud-Stammverzeichnis", "Bitte zuerst unter Datei > Stammdaten das lokale Nextcloud-Stammverzeichnis auswählen.")
            return None
        base = Path(base_text).expanduser()
        try:
            base = base.resolve()
        except Exception:
            pass
        if not base.exists() or not base.is_dir():
            if show_message:
                messagebox.showwarning("Nextcloud-Stammverzeichnis", f"Das eingestellte Nextcloud-Stammverzeichnis wurde nicht gefunden:\n{base}")
            return None
        # Schutz gegen versehentliches Scannen des EXE-/Programmordners.
        try:
            forbidden_names = {"_internal", "app", "pypdf", "PIL", "tk_data", "tcl", "tcl8", "python"}
            child_names = {c.name for c in base.iterdir() if c.is_dir()}
            if "_internal" in child_names and ("app" in child_names or "pypdf" in child_names or "PIL" in child_names):
                if show_message:
                    messagebox.showwarning(
                        "Nextcloud-Stammverzeichnis",
                        "Das eingestellte Verzeichnis sieht wie der Programmordner der EXE aus, nicht wie der Nextcloud-Stammordner.\n\n"
                        "Bitte unter Datei > Stammdaten den Ordner z. B. C:\\Nextcloud_OC auswählen."
                    )
                return None
        except Exception:
            pass
        return base

    def load_folders_from_config(self) -> None:
        if self.nextcloud_base_path(show_message=False):
            self.load_writable_folders(show_message=False)

    def display_path_for_folder(self, path: Path, base: Path) -> str:
        try:
            rel = path.relative_to(base)
            return self.normalize_local_path_text(base) if str(rel) == "." else self.normalize_local_path_text(rel)
        except ValueError:
            return str(path)

    def choose_upload_target_tree(self) -> None:
        """Zielordner für Upload komfortabel als Baum auswählen."""
        if self.nextcloud_base_path(show_message=True) is None:
            return
        if not self.writable_folders:
            self.load_writable_folders(show_message=False)
        selected = self.open_folder_tree_dialog("Zielordner Nextcloud auswählen", self.writable_folders, self.target_folder_var.get())
        if selected:
            base = Path(self.base_folder_var.get().strip()).expanduser()
            display = self.display_path_for_folder(selected, base)
            self.target_folder_map[display] = selected
            values = list(self.target_combo["values"])
            if display not in values:
                values.append(display)
                values.sort(key=str.lower)
                self.target_combo["values"] = values
            self.target_folder_var.set(display)

    def select_combobox_path(self, var: tk.StringVar, combo: ttk.Combobox, mapping: dict[str, Path], path: Path) -> None:
        base = self.nextcloud_base_path(show_message=False) or Path(self.base_folder_var.get().strip()).expanduser()
        display = self.display_path_for_folder(path, base)
        mapping[display] = path
        values = list(combo["values"])
        if display not in values:
            values.append(display)
            values.sort(key=str.lower)
            combo["values"] = values
        var.set(display)

    def is_path_under_base(self, path: Path, base: Path) -> bool:
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    def open_folder_tree_dialog(self, title: str, folders: list[Path], current_display: str = "") -> Path | None:
        """Öffnet einen modalen Baumdialog für beschreibbare Zielordner.

        Kontextordner werden angezeigt, wenn darunter beschreibbare Ordner liegen.
        Auswählbar sind nur tatsächlich beschreibbare Ordner aus ``folders``.
        """
        base = self.nextcloud_base_path(show_message=True)
        if base is None:
            return None
        writable = {str(Path(f).resolve()) for f in folders if Path(f).exists() and self.is_path_under_base(Path(f), base)}
        if not writable:
            messagebox.showwarning("Keine Zielordner", "Es wurden keine beschreibbaren Zielordner gefunden.")
            return None

        dlg = tk.Toplevel(self)
        dlg.title(title)
        try: self.track_window_geometry(dlg, title)
        except Exception: pass
        dlg.geometry("820x620")
        dlg.transient(self)
        dlg.grab_set()
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        info = ttk.Label(
            dlg,
            text="Bitte Zielordner auswählen. Graue Ordner dienen nur der Struktur; auswählbar sind beschreibbare Ordner.",
        )
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        frame = ttk.Frame(dlg)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=("path",), show="tree")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree.tag_configure("writable", foreground="black")
        tree.tag_configure("context", foreground="#777777")

        nodes: dict[tuple[str, ...], str] = {}
        path_by_iid: dict[str, Path] = {}
        writable_iids: set[str] = set()

        def rel_parts(path: Path) -> tuple[str, ...]:
            try:
                rel = path.relative_to(base)
                if str(rel) == ".":
                    return (base.name or str(base),)
                return tuple(rel.parts)
            except ValueError:
                return tuple(path.parts)

        for folder in sorted(folders, key=lambda p: str(p).lower()):
            parts = rel_parts(folder)
            for i in range(1, len(parts) + 1):
                prefix = parts[:i]
                if prefix in nodes:
                    continue
                parent_prefix = parts[: i - 1]
                parent_iid = nodes.get(parent_prefix, "")
                # Pfad zum Präfix rekonstruieren.
                try:
                    if len(prefix) == 1 and prefix[0] == (base.name or str(base)):
                        prefix_path = base
                    else:
                        prefix_path = base.joinpath(*prefix)
                except Exception:
                    prefix_path = folder
                is_writable = str(prefix_path.resolve()) in writable if prefix_path.exists() else False
                iid = tree.insert(parent_iid, "end", text=prefix[-1], values=(str(prefix_path),), tags=("writable" if is_writable else "context",))
                nodes[prefix] = iid
                path_by_iid[iid] = prefix_path
                if is_writable:
                    writable_iids.add(iid)

        # Aktuellen Ordner markieren, falls möglich.
        current_path = None
        if current_display:
            current_path = self.target_folder_map.get(current_display) or getattr(self, "admin_destination_map", {}).get(current_display)
        if current_path:
            current_resolved = str(Path(current_path).resolve())
            for iid, pth in path_by_iid.items():
                if pth.exists() and str(pth.resolve()) == current_resolved:
                    tree.selection_set(iid)
                    tree.see(iid)
                    break

        selected_path: list[Path | None] = [None]

        def accept() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Keine Auswahl", "Bitte einen Zielordner auswählen.", parent=dlg)
                return
            iid = sel[0]
            path = path_by_iid.get(iid)
            if not path or str(path.resolve()) not in writable:
                tree.item(iid, open=True)
                messagebox.showwarning("Nicht auswählbar", "Dieser Ordner dient nur der Struktur. Bitte einen beschreibbaren Zielordner auswählen.", parent=dlg)
                return
            selected_path[0] = path
            dlg.destroy()

        tree.bind("<Double-1>", lambda _e: accept())
        buttons = ttk.Frame(dlg)
        buttons.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 10))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Ordner übernehmen", command=accept).grid(row=0, column=1, sticky="e", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=dlg.destroy).grid(row=0, column=2, sticky="e", padx=4)

        self.wait_window(dlg)
        return selected_path[0]

    def load_writable_folders(self, show_message: bool = True) -> None:
        if getattr(self, "_loading_writable_folders", False):
            return
        self._loading_writable_folders = True
        try:
            base = self.nextcloud_base_path(show_message=show_message)
            if base is None:
                self.writable_folders = []
                self.target_folder_map = {}
                if hasattr(self, "target_combo"):
                    self.target_combo["values"] = []
                if hasattr(self, "target_folder_var"):
                    self.target_folder_var.set("")
                if hasattr(self, "file_view_combo"):
                    self.refresh_file_view_folder_choices()
                return
            self.ensure_standard_metadata_folder()
            self.writable_folders = find_writable_folders(base)
            metadata_folder = self.metadata_folder_path()
            filtered: list[Path] = []
            for folder in self.writable_folders:
                try:
                    if folder == metadata_folder or metadata_folder in folder.parents:
                        continue
                except Exception:
                    pass
                if not self.is_folder_allowed_for_current_user(folder, base):
                    continue
                filtered.append(folder)
            self.writable_folders = filtered
            self.target_folder_map = {self.display_path_for_folder(path, base): path for path in self.writable_folders}
            values = sorted(self.target_folder_map.keys(), key=str.lower)
            if hasattr(self, "target_combo"):
                self.target_combo["values"] = values
            if values and self.target_folder_var.get() not in values:
                self.target_folder_var.set(self.default_upload_target() or values[0])
            elif not values:
                self.target_folder_var.set("")
            if hasattr(self, "file_view_combo"):
                self.refresh_file_view_folder_choices()
            if hasattr(self, "admin_destination_combo"):
                self.refresh_admin_destination_choices()
            self.update_connection_status()
            app_log("info", "Zielordner geprüft", count=len(values), user=self.username_var.get())
            if show_message:
                messagebox.showinfo("Ordnerprüfung", f"{len(values)} beschreibbare Zielordner gefunden.")
        finally:
            self._loading_writable_folders = False

