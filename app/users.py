from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .config import APP_DIR, ensure_app_dir

USERS_FILE = APP_DIR / "users.json"
ROLES = ["Ortschronist", "Admin", "Superadmin"]


def normalize_username(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9_\-.]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "benutzer"


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    return hash_password(password, salt).split("$", 2)[2] == digest


def default_users(display_name: str | None = None) -> list[dict[str, Any]]:
    name = (display_name or "Superadmin").strip() or "Superadmin"
    username = normalize_username(name if name != "Superadmin" else "superadmin")
    return [
        {
            "display_name": name,
            "username": username,
            "password_hash": hash_password("admin"),
            "role": "Superadmin",
            "place": "",
            "active": True,
        }
    ]


def normalize_user(item: dict[str, Any], fallback_name: str | None = None) -> dict[str, Any] | None:
    name = str(item.get("display_name") or item.get("name") or fallback_name or "").strip()
    if not name:
        return None
    username = str(item.get("username") or normalize_username(name)).strip()
    role = str(item.get("role", "Ortschronist")).strip()
    if role not in ROLES:
        role = "Ortschronist"
    place = str(item.get("place") or item.get("area") or "").strip()
    password_hash = str(item.get("password_hash") or "").strip()
    if not password_hash:
        # Migrationshilfe für alte MVP-Benutzer: Standardpasswort admin.
        # Danach kann der Superadmin das Passwort in der Benutzerverwaltung ändern.
        password_hash = hash_password("admin")
    return {
        "display_name": name,
        "username": normalize_username(username),
        "password_hash": password_hash,
        "role": role,
        "place": place,
        "active": bool(item.get("active", True)),
    }


def ensure_unique_usernames(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for user in users:
        base = normalize_username(str(user.get("username", "benutzer")))
        username = base
        counter = 2
        while username in seen:
            username = f"{base}_{counter}"
            counter += 1
        user["username"] = username
        seen.add(username)
        result.append(user)
    return result


def load_users(initial_display_name: str | None = None) -> list[dict[str, Any]]:
    ensure_app_dir()
    changed = False
    if not USERS_FILE.exists():
        users = default_users(initial_display_name)
        save_users(users)
        return users
    try:
        with USERS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = []
    if not isinstance(data, list) or not data:
        users = default_users(initial_display_name)
        save_users(users)
        return users
    normalized: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        user = normalize_user(item, initial_display_name)
        if user:
            normalized.append(user)
            if user != item:
                changed = True
    if not normalized:
        normalized = default_users(initial_display_name)
        changed = True
    normalized = ensure_unique_usernames(normalized)
    if changed:
        save_users(normalized)
    return normalized


def save_users(users: list[dict[str, Any]]) -> None:
    ensure_app_dir()
    normalized = ensure_unique_usernames([u.copy() for u in users])
    with USERS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2)


def find_user_by_name(users: list[dict[str, Any]], display_name: str) -> dict[str, Any] | None:
    wanted = display_name.strip().lower()
    for user in users:
        if str(user.get("display_name", "")).strip().lower() == wanted:
            return user
    return None


def find_user_by_username(users: list[dict[str, Any]], username: str) -> dict[str, Any] | None:
    wanted = normalize_username(username)
    for user in users:
        if normalize_username(str(user.get("username", ""))) == wanted:
            return user
    return None


# Rückwärtskompatibilität zu älterem Code.
def find_user(users: list[dict[str, Any]], display_name: str) -> dict[str, Any] | None:
    return find_user_by_name(users, display_name)


def role_allows_admin(role: str) -> bool:
    return role in {"Admin", "Superadmin"}


def role_allows_user_management(role: str) -> bool:
    return role == "Superadmin"
