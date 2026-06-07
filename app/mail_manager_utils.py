from __future__ import annotations

import html
import re


def coerce_user_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("users", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if any(isinstance(v, (str, int, bool)) for v in payload.values()):
            return [payload]
    return []


def extract_user_email(user: dict) -> str:
    direct_keys = ("email", "mail", "mail_address", "mailadresse", "e_mail", "eMail", "mailAddress")
    for key in direct_keys:
        value = str(user.get(key, "") or "").strip()
        if value:
            return value
    nested_paths = (
        ("contact", "email"),
        ("contact", "mail"),
        ("address", "email"),
        ("address", "mail"),
        ("kontakt", "email"),
        ("kontakt", "mail"),
    )
    for outer, inner in nested_paths:
        nested = user.get(outer)
        if isinstance(nested, dict):
            value = str(nested.get(inner, "") or "").strip()
            if value:
                return value
    return ""


def extract_user_active(user: dict) -> bool:
    active_value = user.get("is_active", user.get("active", user.get("enabled", True)))
    if isinstance(active_value, str):
        return active_value.strip().lower() in {"1", "true", "yes", "ja", "active", "aktiv"}
    return bool(active_value)


def extract_numeric_user_id(user: dict, keys: tuple[str, ...] = ("id", "user_id", "uid", "userId")) -> int:
    for key in keys:
        raw_id = user.get(key)
        if raw_id is None:
            continue
        try:
            value = int(raw_id)
            if value != 0:
                return value
        except Exception:
            continue
    return 0


def build_stable_user_id(item: dict, email: str) -> int:
    if numeric_id := extract_numeric_user_id(item):
        return numeric_id
    return -abs(hash((item.get("username", ""), email, item.get("display_name", "")))) or -1


def normalize_mail_markup(text: str) -> str:
    return re.sub(r"/b(.*?)/b", lambda m: m.group(1), text or "", flags=re.S)


def render_mail_html(text: str) -> str:
    """Erzeugt eine sehr leichte HTML-Darstellung mit /b.../b als fett."""
    parts: list[str] = []
    last = 0
    raw = text or ""
    for match in re.finditer(r"/b(.*?)/b", raw, flags=re.S):
        if match.start() > last:
            parts.append(html.escape(raw[last:match.start()]))
        parts.append(f"<strong>{html.escape(match.group(1))}</strong>")
        last = match.end()
    if last < len(raw):
        parts.append(html.escape(raw[last:]))
    html_text = "".join(parts)
    html_text = html_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>\n")
    return f"<html><body>{html_text}</body></html>"

