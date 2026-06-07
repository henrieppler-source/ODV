from __future__ import annotations

import json
import urllib.error
import urllib.request
import urllib.parse
from typing import Any


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, response: Any = None):
        super().__init__(message)
        self.status = status
        self.response = response


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = (base_url or "").rstrip("/")

    def configured(self) -> bool:
        return bool(self.base_url)

    def request(self, method: str, path: str, data: dict | None = None, token: str | None = None) -> dict:
        if not self.base_url:
            raise ApiError("Keine API-URL konfiguriert")
        url = self.base_url + (path if path.startswith("/") else "/" + path)
        body = None
        headers = {"Accept": "application/json"}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw}
            msg = payload.get("error") or payload.get("message") or f"HTTP-Fehler {exc.code}"
            raise ApiError(str(msg), exc.code, payload) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"API nicht erreichbar: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ApiError("Zeitüberschreitung beim API-Aufruf") from exc
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ApiError("API hat keine gültige JSON-Antwort geliefert") from exc
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ApiError(str(payload.get("error") or payload.get("message") or "API-Fehler"), response=payload)
        if not isinstance(payload, dict):
            raise ApiError("API-Antwort hat unerwartetes Format")
        return payload

    def status(self) -> dict:
        return self.request("GET", "/status")

    def app_update(self, token: str | None = None) -> dict:
        return self.request("GET", "/app-update", token=token)

    def update_app_release(self, token: str, payload: dict) -> dict:
        return self.request("PUT", "/admin/app-update", payload, token=token)

    def login(self, username: str, password: str, device_info: dict | None = None) -> dict:
        payload = {"username": username, "password": password}
        if device_info:
            payload["device"] = device_info
        return self.request("POST", "/login", payload)

    def me(self, token: str) -> dict:
        return self.request("GET", "/me", token=token)

    def update_session_device(self, token: str, device_info: dict) -> dict:
        return self.request("POST", "/session/device", {"device": device_info}, token=token)

    def logout(self, token: str) -> dict:
        return self.request("POST", "/logout", token=token)

    def create_document(self, token: str, payload: dict) -> dict:
        return self.request("POST", "/documents", payload, token=token)

    def list_documents(self, token: str, status: str | None = None, only_own: bool = False) -> dict:
        params = {}
        if status and status != "alle":
            params["status"] = status
        if only_own:
            params["only_own"] = "1"
        query = ("?" + urllib.parse.urlencode(params)) if params else ""
        return self.request("GET", "/documents" + query, token=token)

    def get_document(self, token: str, upload_id: str) -> dict:
        return self.request("GET", f"/documents/{urllib.parse.quote(upload_id, safe='')}", token=token)

    def update_document(self, token: str, upload_id: str, payload: dict) -> dict:
        return self.request("PUT", f"/documents/{urllib.parse.quote(upload_id, safe='')}", payload, token=token)

    def update_persons(self, token: str, upload_id: str, persons: list[dict]) -> dict:
        return self.request("PUT", f"/documents/{urllib.parse.quote(upload_id, safe='')}/persons", {"persons": persons}, token=token)

    def list_users(self, token: str) -> dict:
        return self.request("GET", "/users", token=token)

    def create_user(self, token: str, payload: dict) -> dict:
        return self.request("POST", "/users", payload, token=token)

    def update_user(self, token: str, user_id: int, payload: dict) -> dict:
        return self.request("PUT", f"/users/{int(user_id)}", payload, token=token)
    def get_user(self, token: str, user_id: int) -> dict:
        return self.request("GET", f"/users/{int(user_id)}", token=token)
    def get_folder_permissions(self, token: str, user_id: int | None = None) -> dict:
        if user_id is None:
            return self.request("GET", "/folder-permissions", token=token)
        return self.request("GET", f"/users/{int(user_id)}/folder-permissions", token=token)

    def update_folder_permissions(self, token: str, user_id: int, permissions: list[dict]) -> dict:
        return self.request("PUT", f"/users/{int(user_id)}/folder-permissions", {"permissions": permissions}, token=token)

    def list_place_folders(self, token: str) -> dict:
        return self.request("GET", "/place-folders", token=token)

    def update_place_folders(self, token: str, places: list[dict]) -> dict:
        return self.request("PUT", "/place-folders", {"places": places}, token=token)


    def list_mail_groups(self, token: str) -> dict:
        return self.request("GET", "/mail-groups", token=token)

    def update_mail_groups(self, token: str, groups: list[dict]) -> dict:
        return self.request("PUT", "/mail-groups", {"groups": groups}, token=token)

    def send_mail(self, token: str, payload: dict) -> dict:
        return self.request("POST", "/mails/send", payload, token=token)



    def list_sessions_and_devices(self, token: str) -> dict:
        return self.request("GET", "/admin/sessions", token=token)

    def end_session(self, token: str, session_id: int) -> dict:
        return self.request("POST", "/admin/sessions/end", {"session_id": int(session_id)}, token=token)

    def set_device_blocked(self, token: str, user_id: int, device_id: str, blocked: bool) -> dict:
        return self.request("POST", "/admin/devices/block", {"user_id": int(user_id), "device_id": device_id, "blocked": bool(blocked)}, token=token)

    def lock_document(self, token: str, upload_id: str) -> dict:
        return self.request("POST", f"/documents/{urllib.parse.quote(upload_id, safe='')}/lock", token=token)

    def unlock_document(self, token: str, upload_id: str) -> dict:
        return self.request("DELETE", f"/documents/{urllib.parse.quote(upload_id, safe='')}/lock", token=token)

    def log_document_access(self, token: str, upload_id: str, action: str, local_path: str = "") -> dict:
        return self.request("POST", f"/documents/{urllib.parse.quote(upload_id, safe='')}/access-log", {
            "action": action,
            "local_path": local_path,
        }, token=token)

    def document_access_log(self, token: str, limit: int = 500) -> dict:
        return self.request("GET", f"/document-access-log?limit={int(limit)}", token=token)

    def mail_history(self, token: str, limit: int = 200) -> dict:
        return self.request("GET", f"/mails/history?limit={int(limit)}", token=token)


    def maintenance_status(self, token: str | None = None) -> dict:
        return self.request("GET", "/admin/maintenance", token=token)

    def operating_mode(self, token: str) -> dict:
        return self.request("GET", "/admin/operating-mode", token=token)

    def set_operating_mode(self, token: str, mode: str) -> dict:
        return self.request("POST", "/admin/operating-mode", {"mode": mode}, token=token)

    def set_maintenance(self, token: str, minutes: int, message: str = "") -> dict:
        return self.request("POST", "/admin/maintenance", {"action": "schedule", "minutes": int(minutes), "message": message}, token=token)

    def clear_maintenance(self, token: str) -> dict:
        return self.request("POST", "/admin/maintenance", {"action": "clear"}, token=token)

    def nextcloud_settings(self, token: str) -> dict:
        return self.request("GET", "/admin/nextcloud-settings", token=token)

    def update_nextcloud_settings(self, token: str, payload: dict) -> dict:
        return self.request("PUT", "/admin/nextcloud-settings", payload, token=token)

    def test_nextcloud_settings(self, token: str, payload: dict) -> dict:
        return self.request("POST", "/admin/nextcloud-settings/test", payload, token=token)

    def create_database_backup(self, token: str) -> dict:
        return self.request("POST", "/admin/backup", {}, token=token)

    def backup_status(self, token: str) -> dict:
        return self.request("GET", "/admin/backup-status", token=token)

    def list_database_backups(self, token: str) -> dict:
        return self.request("GET", "/admin/backups", token=token)

    def restore_database_backup(self, token: str, file: str, confirm_text: str) -> dict:
        return self.request("POST", "/admin/restore-backup", {
            "file": file,
            "confirm_text": confirm_text,
        }, token=token)

    def schema_migrations(self, token: str) -> dict:
        return self.request("GET", "/admin/schema-migrations", token=token)

    def pending_migrations(self, token: str) -> dict:
        return self.schema_migrations(token)

    def apply_schema_migrations(self, token: str) -> dict:
        return self.request("POST", "/admin/schema-migrations/apply", {}, token=token)

    def reset_database(self, token: str, confirm_text: str, include_mail_history: bool = True) -> dict:
        return self.request("POST", "/admin/reset-database", {
            "confirm_text": confirm_text,
            "include_mail_history": bool(include_mail_history),
        }, token=token)

    def create_nextcloud_share(self, token: str, local_file_path: str, local_nextcloud_base: str, share_expires_at: str = "") -> dict:
        payload = {
            "local_file_path": local_file_path,
            "local_nextcloud_base": local_nextcloud_base,
        }
        if share_expires_at:
            payload["share_expires_at"] = share_expires_at
        return self.request("POST", "/nextcloud/share", payload, token=token)

    def list_point_rules(self, token: str, year: int | None = None) -> dict:
        query = f"?year={int(year)}" if year else ""
        return self.request("GET", "/point-rules" + query, token=token)

    def update_point_rules(self, token: str, year: int, rules: list[dict]) -> dict:
        return self.request("PUT", "/point-rules", {"year": int(year), "rules": rules}, token=token)

    def points_summary(self, token: str, year: int) -> dict:
        return self.request("GET", f"/points/summary?year={int(year)}", token=token)

    def points_year_status(self, token: str, year: int) -> dict:
        return self.request("GET", f"/points/year-status?year={int(year)}", token=token)

    def set_points_year_budget(self, token: str, year: int, budget: str | float | int) -> dict:
        return self.request("PUT", "/points/year-budget", {"year": int(year), "budget": budget}, token=token)

    def close_points_year(self, token: str, year: int, note: str = "") -> dict:
        payload = {"year": int(year)}
        if note:
            payload["note"] = note
        return self.request("POST", "/points/year-close", payload, token=token)

    def reopen_points_year(self, token: str, year: int) -> dict:
        return self.request("POST", "/points/year-reopen", {"year": int(year)}, token=token)

    def my_points(self, token: str, year: int, user_id: int | None = None) -> dict:
        params = {"year": int(year)}
        if user_id is not None:
            params["user_id"] = int(user_id)
        return self.request("GET", "/points/me?" + urllib.parse.urlencode(params), token=token)

    def document_points(self, token: str, upload_id: str) -> dict:
        return self.request("GET", f"/documents/{urllib.parse.quote(upload_id, safe='')}/points", token=token)

    def recalculate_document_points(self, token: str, upload_id: str) -> dict:
        return self.request("POST", f"/documents/{urllib.parse.quote(upload_id, safe='')}/points/recalculate", {}, token=token)

    def recalculate_points_bulk(self, token: str, upload_ids: list[str]) -> dict:
        return self.request("POST", "/points/recalculate-bulk", {"upload_ids": list(upload_ids)}, token=token)

    def add_manual_points(self, token: str, upload_id: str, user_id: int, points: int, reason: str, category: str = "manual_bonus", rule_key: str = "", source_field: str = "") -> dict:
        payload = {
            "user_id": int(user_id), "points": int(points), "reason": reason, "category": category
        }
        if rule_key:
            payload["rule_key"] = rule_key
        if source_field:
            payload["source_field"] = source_field
        return self.request("POST", f"/documents/{urllib.parse.quote(upload_id, safe='')}/manual-points", payload, token=token)

    def update_manual_document_points(self, token: str, point_id: int, user_id: int, points: int, reason: str, category: str = "manual_bonus", rule_key: str = "", source_field: str = "") -> dict:
        payload = {
            "user_id": int(user_id), "points": int(points), "reason": reason, "category": category
        }
        if rule_key:
            payload["rule_key"] = rule_key
        if source_field:
            payload["source_field"] = source_field
        return self.request("PUT", f"/document-manual-points/{int(point_id)}", payload, token=token)

    def delete_manual_document_points(self, token: str, point_id: int) -> dict:
        return self.request("DELETE", f"/document-manual-points/{int(point_id)}", token=token)

    def list_manual_special_points(self, token: str, year: int | None = None) -> dict:
        params = {}
        if year is not None:
            params["year"] = int(year)
        suffix = "?" + urllib.parse.urlencode(params) if params else ""
        return self.request("GET", "/manual-points" + suffix, token=token)

    def add_manual_special_points(self, token: str, user_id: int, rule_key: str, points: int, reason: str, activity_date: str = "", hours: float | None = None, note: str = "") -> dict:
        payload = {
            "user_id": int(user_id),
            "rule_key": rule_key,
            "points": int(points),
            "reason": reason,
            "activity_date": activity_date,
            "note": note,
        }
        if hours is not None:
            payload["hours"] = float(hours)
        return self.request("POST", "/manual-points", payload, token=token)

    def get_manual_points_settings(self, token: str) -> dict:
        return self.request("GET", "/admin/manual-points-settings", token=token)

    def save_manual_points_settings(self, token: str, points_per_hour: int) -> dict:
        return self.request("PUT", "/admin/manual-points-settings", {"points_per_hour": int(points_per_hour)}, token=token)
