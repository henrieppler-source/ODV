from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .secure_store import SecureStoreError, protect_text, unprotect_text

def default_app_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Programs" / "ODV"
    return Path.home() / "AppData" / "Local" / "Programs" / "ODV"


LEGACY_APP_DIR = Path.home() / ".ortschronik_uploader"
APP_DIR = default_app_dir()
CONFIG_FILE = APP_DIR / "config.json"
DB_FILE = APP_DIR / "history.sqlite"

DEFAULT_CONFIG: dict[str, Any] = {
    "display_name": "Ortschronist/in",
    "current_username": "",
    "current_email": "",
    "nextcloud_base_folder": "",
    "metadata_folder": "",
    "metadata_folder_name": ".ortschronik_metadaten",
    "admin_work_folder_names": ["01_ABLAGE_ORTSCHRONIK", "06_ARBEIT_DER_ORTSCHRONISTEN"],
    "last_seen_history_at": None,
    "current_role": "Admin",
    "current_place": "",
    "api_url": "https://ortschronik.info/api",
    "api_token": "",
    "api_token_expires_at": "",
    "api_token_dpapi": "",
    "openai_api_key": "",
    "openai_api_key_dpapi": "",
    "openai_model": "gpt-3.5-turbo",
    "openai_pdf_sample_pages": 10,
    "openai_text_sample_chars": 4000,
    "openai_metadata_points": 1,
    "archive_collection_options": [],
    "mail_text_templates": [],
    "mysql_host": "",
    "mysql_port": "3306",
    "mysql_database": "",
    "mysql_user": "",
    "ftp_host": "w0210fa6.kasserver.com",
    "ftp_port": "21",
    "ftp_user": "f0185adc",
    "ftp_remote_routes_path": "/ortschronik.info/ortschronik-api/routes.php",
    "ftp_local_routes_path": "server/routes.php",
    "ftp_password_dpapi": "",
    "nextcloud_web_files_url": "https://nx94165.your-storageshare.de/apps/files/files",
    "device_id": "",
}

SENSITIVE_CONFIG_FIELDS = {
    "api_token": "api_token_dpapi",
    "openai_api_key": "openai_api_key_dpapi",
}


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if LEGACY_APP_DIR.exists() and LEGACY_APP_DIR != APP_DIR:
        for name in ("config.json", "users.json", "history.sqlite"):
            old = LEGACY_APP_DIR / name
            new = APP_DIR / name
            if old.exists() and not new.exists():
                try:
                    shutil.copy2(old, new)
                except Exception:
                    pass
        old_logs = LEGACY_APP_DIR / "logs"
        new_logs = APP_DIR / "logs"
        if old_logs.exists() and not new_logs.exists():
            try:
                shutil.copytree(old_logs, new_logs)
            except Exception:
                pass


def load_config() -> dict[str, Any]:
    ensure_app_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    with CONFIG_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    for plain_key, dpapi_key in SENSITIVE_CONFIG_FIELDS.items():
        encrypted = str(merged.get(dpapi_key, "") or "").strip()
        if encrypted:
            try:
                merged[plain_key] = unprotect_text(encrypted)
                continue
            except SecureStoreError:
                pass
        merged[plain_key] = str(merged.get(plain_key, "") or "")
    return merged


def save_config(config: dict[str, Any]) -> None:
    ensure_app_dir()
    data = dict(config)
    for plain_key, dpapi_key in SENSITIVE_CONFIG_FIELDS.items():
        plain_value = str(data.get(plain_key, "") or "").strip()
        if plain_value:
            try:
                data[dpapi_key] = protect_text(plain_value)
                data.pop(plain_key, None)
            except SecureStoreError:
                data[dpapi_key] = ""
                data[plain_key] = plain_value
        else:
            data[dpapi_key] = ""
            data.pop(plain_key, None)
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
