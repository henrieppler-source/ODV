from __future__ import annotations

from tkinter import messagebox

from .app_logging import app_log_exception


class AdminPointsManagerMixin:
    def update_admin_document_points_display(self, upload_id: str) -> None:
        if not upload_id or not self.api_token:
            self.admin_document_points_var.set("keine Punkte geladen")
            return
        try:
            resp = self.api.document_points(self.api_token, upload_id)
            rows = resp.get("points", []) or []
            total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1)
            auto_total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1 and int(r.get("is_manual", 0) or 0) == 0)
            manual_total = sum(int(float(r.get("points", 0) or 0)) for r in rows if int(r.get("is_confirmed", 1) or 0) == 1 and int(r.get("is_manual", 0) or 0) == 1)
            if not rows:
                self.admin_document_points_var.set("0")
            else:
                self.admin_document_points_var.set(f"{total} gesamt · automatisch {auto_total} · Sonder {manual_total}")
        except Exception as exc:
            self.admin_document_points_var.set("nicht geladen")
            app_log_exception("Dokumentpunkte konnten nicht geladen werden", exc, upload_id=upload_id)

    def recalculate_points_for_visible_admin_uploads(self) -> None:
        """Berechnet fehlende automatische Punkte für alle aktuell angezeigten Admin-Datensätze nach."""
        if self.current_role() != "Superadmin":
            messagebox.showwarning("Keine Berechtigung", "Diese Nachberechnung ist nur für Superadmins freigegeben.")
            return
        if not self.api_token:
            messagebox.showwarning("Nicht angemeldet", "Für die Punkteberechnung ist eine API-Anmeldung erforderlich.")
            return
        upload_ids: list[str] = []
        def collect(node: str) -> None:
            values = self.file_tree.item(node, "values")
            path_text = values[0] if values else ""
            item = self.item_for_local_path(path_text) if path_text else None
            upload_id = str((item or {}).get("upload_id") or "").strip()
            if upload_id and not upload_id.startswith("__missing_odv__"):
                upload_ids.append(upload_id)
            for child in self.file_tree.get_children(node):
                collect(child)

        if self.notebook.select() == str(self.viewer_tab):
            for root in self.file_tree.get_children(""):
                collect(root)
        else:
            upload_ids = list(self.admin_tree.get_children(""))
        upload_ids = list(dict.fromkeys(upload_ids))
        if not upload_ids:
            messagebox.showinfo("Punkte", "In der aktuellen Liste sind keine Dateien vorhanden.")
            return
        if not messagebox.askyesno(
            "Punkte nachtragen",
            f"Für {len(upload_ids)} aktuell angezeigte Dateien fehlende automatische Punkte nachträglich ermitteln?\n\n"
            "Bereits vorhandene Punkte werden nicht doppelt gespeichert.",
        ):
            return
        try:
            resp = self.api.recalculate_points_bulk(self.api_token, upload_ids)
            processed = int(resp.get("processed", 0) or 0)
            eligible = int(resp.get("eligible", 0) or 0)
            created = int(resp.get("created", 0) or 0)
            skipped_existing = int(resp.get("skipped_existing", 0) or 0)
            skipped_ineligible = int(resp.get("skipped_ineligible", 0) or 0)
            messagebox.showinfo(
                "Punkte",
                f"Verarbeitet: {processed}\nPunkteberechtigt: {eligible}\nNeu angelegt: {created}\nSchon vorhanden: {skipped_existing}\nNicht berechtigt: {skipped_ineligible}",
            )
            self.refresh_document_work_area(show_message=False)
        except Exception as exc:
            messagebox.showerror("Punkte", str(exc))
            app_log_exception("Punkte-Nachberechnung für angezeigte Liste fehlgeschlagen", exc)
