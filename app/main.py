from __future__ import annotations

import atexit
import tkinter as tk
from tkinter import messagebox

from .single_instance import acquire_single_instance_lock, release_single_instance_lock
from .uploader import OrtschronikUploader


def main() -> None:
    if not acquire_single_instance_lock():
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                "ODV läuft bereits",
                "ODV ist bereits geöffnet oder wird gerade aktualisiert.\n\n"
                "Bitte warten Sie, bis das laufende Fenster geschlossen ist.",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
        return
    atexit.register(release_single_instance_lock)
    app = OrtschronikUploader()
    app.mainloop()


if __name__ == "__main__":
    main()
