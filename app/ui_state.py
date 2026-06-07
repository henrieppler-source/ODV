from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

from .app_logging import app_log_exception
from .config import save_config


class UiStateMixin:
    def bind_global_mousewheel(self) -> None:
        """Mausrad soll in dem Bereich scrollen, über dem der Mauszeiger steht."""
        def scroll_widget(widget, delta: int):
            current = widget
            while current is not None:
                try:
                    current.yview_scroll(delta, "units")
                    return "break"
                except Exception:
                    pass
                current = current.master
            return None

        def on_mousewheel(event):
            try:
                widget = self.winfo_containing(event.x_root, event.y_root)
                delta = -1 if event.delta > 0 else 1
                return scroll_widget(widget, delta)
            except Exception:
                return None

        def on_button4(event):
            widget = self.winfo_containing(event.x_root, event.y_root)
            return scroll_widget(widget, -1)

        def on_button5(event):
            widget = self.winfo_containing(event.x_root, event.y_root)
            return scroll_widget(widget, 1)

        self.bind_all("<MouseWheel>", on_mousewheel, add="+")
        self.bind_all("<Button-4>", on_button4, add="+")
        self.bind_all("<Button-5>", on_button5, add="+")

    def create_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("Dashboard.TFrame", background="#eeeeee")
        style.configure("Upload.TFrame", background="#eeeeee")
        style.configure("Viewer.TFrame", background="#eeeeee")
        style.configure("Admin.TFrame", background="#eeeeee")
        style.configure("Hint.TLabel", padding=2)
        try:
            default_font = tkfont.nametofont("TkDefaultFont")
            self.tab_font_normal = default_font.copy()
            self.tab_font_bold = default_font.copy()
            self.tab_font_bold.configure(weight="bold")
            style.map("TNotebook.Tab", font=[("selected", self.tab_font_bold), ("!selected", self.tab_font_normal)])
            style.configure("Treeview.Heading", font=self.tab_font_bold)
        except Exception:
            pass

    def update_tab_labels(self) -> None:
        names = {
            str(self.history_tab): "Dashboard",
            str(self.upload_tab_container): "Dateien hochladen",
            str(self.viewer_tab): "Dateien anzeigen/bearbeiten",
        }
        try:
            selected = self.notebook.select()
            for tab_id in self.notebook.tabs():
                base = names.get(tab_id, self.notebook.tab(tab_id, "text").replace("● ", ""))
                self.notebook.tab(tab_id, text=("● " + base if tab_id == selected else "  " + base))
        except tk.TclError:
            pass

    def on_notebook_tab_changed(self, _event=None) -> None:
        self.update_tab_labels()
        self.update_connection_status()
        try:
            selected = self.notebook.select()
            if selected == str(self.history_tab):
                self.refresh_history()
            if selected == str(self.viewer_tab):
                self.refresh_file_view_folder_choices()
                self.refresh_file_view_tree()
                self.clear_file_view_selection()
        except Exception as exc:
            app_log_exception("Reiterwechsel konnte nicht vollständig verarbeitet werden", exc)

    def maximize_window(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def ui_settings(self) -> dict:
        data = self.config_data.setdefault("ui_settings", {})
        if not isinstance(data, dict):
            data = {}
            self.config_data["ui_settings"] = data
        return data

    def _window_state_key(self, key: str) -> str:
        text = str(key or "window").strip().lower()
        text = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")
        return text or "window"

    def _geometry_is_reasonable(self, geometry: str) -> bool:
        try:
            m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(geometry or ""))
            if not m:
                return False
            w, h, x, y = map(int, m.groups())
            if w < 300 or h < 180:
                return False
            sw = max(800, int(self.winfo_screenwidth() or 0))
            sh = max(600, int(self.winfo_screenheight() or 0))
            if x > sw - 80 or y > sh - 80 or x < -max(200, w - 80) or y < -max(120, h - 80):
                return False
            return True
        except Exception:
            return False

    def restore_window_geometry(self, window: tk.Misc, key: str, default: str | None = None) -> None:
        try:
            k = self._window_state_key(key)
            geometry = str(self.ui_settings().get(k, {}).get("geometry", "") or "")
            if geometry and self._geometry_is_reasonable(geometry):
                window.geometry(geometry)
            elif default:
                window.geometry(default)
        except Exception as exc:
            app_log_exception("Fenstergeometrie konnte nicht wiederhergestellt werden", exc, key=key)

    def save_window_geometry(self, window: tk.Misc, key: str) -> None:
        try:
            if not bool(window.winfo_exists()):
                return
            k = self._window_state_key(key)
            geometry = window.winfo_geometry()
            if not self._geometry_is_reasonable(geometry):
                return
            settings = self.ui_settings().setdefault(k, {})
            settings["geometry"] = geometry
            save_config(self.config_data)
        except Exception:
            pass

    def track_window_geometry(self, window: tk.Misc, key: str, default: str | None = None) -> None:
        """Merkt Größe/Position eines Dialogs lokal je Gerät und stellt sie beim nächsten Öffnen wieder her."""
        k = self._window_state_key(key)

        def _restore_later() -> None:
            try:
                self.restore_window_geometry(window, k, default)
            except Exception:
                pass

        try:
            window.after(120, _restore_later)
        except Exception:
            _restore_later()

        state = {"after_id": None, "last_geometry": ""}

        def _capture_geometry() -> str:
            try:
                if not bool(window.winfo_exists()):
                    return ""
                window.update_idletasks()
                geometry = str(window.winfo_geometry() or "")
                if self._geometry_is_reasonable(geometry):
                    state["last_geometry"] = geometry
                return state["last_geometry"]
            except Exception:
                return ""

        def _save_geometry_now() -> None:
            try:
                geometry = _capture_geometry()
                if not geometry:
                    return
                settings = self.ui_settings().setdefault(k, {})
                settings["geometry"] = geometry
                save_config(self.config_data)
            except Exception:
                pass

        def _schedule_save(event=None) -> None:
            try:
                if event is not None and event.widget is not window:
                    return
                _capture_geometry()
                old_after = state.get("after_id")
                if old_after:
                    try:
                        window.after_cancel(old_after)
                    except Exception:
                        pass
                state["after_id"] = window.after(500, _save_geometry_now)
            except Exception:
                pass

        def _close_window() -> None:
            _save_geometry_now()
            try:
                window.destroy()
            except Exception:
                pass

        def _save_on_destroy(event=None):
            try:
                if event is not None and event.widget is not window:
                    return
                _save_geometry_now()
            except Exception:
                pass

        try:
            window.bind("<Configure>", _schedule_save, add="+")
        except Exception:
            pass
        try:
            window.bind("<Destroy>", _save_on_destroy, add="+")
        except Exception:
            pass
        try:
            window.protocol("WM_DELETE_WINDOW", _close_window)
        except Exception:
            pass

    def on_main_window_close(self) -> None:
        self.save_window_geometry(self, "main_window")
        self.destroy()

    def save_pane_positions(self) -> None:
        try:
            self.config_data["viewer_outer_sash"] = int(self.viewer_outer_pane.sashpos(0))
            self.config_data["viewer_right_sash"] = int(self.viewer_right_pane.sashpos(0))
            self.config_data["admin_outer_sash"] = int(self.admin_outer_pane.sashpos(0))
            self.config_data["admin_right_sash"] = int(self.admin_right_pane.sashpos(0))
            save_config(self.config_data)
        except Exception:
            pass

    def restore_pane_positions(self) -> None:
        try:
            if self.config_data.get("viewer_outer_sash"):
                self.viewer_outer_pane.sashpos(0, int(self.config_data.get("viewer_outer_sash")))
            if self.config_data.get("viewer_right_sash"):
                self.viewer_right_pane.sashpos(0, int(self.config_data.get("viewer_right_sash")))
            if self.config_data.get("admin_outer_sash"):
                self.admin_outer_pane.sashpos(0, int(self.config_data.get("admin_outer_sash")))
            if self.config_data.get("admin_right_sash"):
                self.admin_right_pane.sashpos(0, int(self.config_data.get("admin_right_sash")))
        except Exception:
            pass

    def save_tree_column_widths(self, silent: bool = False) -> None:
        widths = self.config_data.setdefault("tree_column_widths", {})
        widths["history"] = {col: int(self.history_tree.column(col, "width")) for col in self.history_tree["columns"]}
        save_config(self.config_data)
        if not silent:
            messagebox.showinfo("Ansicht", "Spaltenbreiten wurden gespeichert.")
