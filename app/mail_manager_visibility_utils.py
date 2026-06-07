from __future__ import annotations

MAIL_USER_CONTEXT_SOURCE_ATTRS = (
    "current_user",
    "current_user_data",
    "user_data",
    "logged_in_user",
    "session_user",
)


def _pick_from_source(source: object, *keys: str) -> str:
    if isinstance(source, dict):
        data = source
    else:
        try:
            data = vars(source)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        return ""

    for key in keys:
        value = str(data.get(key, "") or "").strip()
        if value:
            return value
    return ""


def mail_user_context(source_obj: object, config_data: object | None = None) -> dict[str, str]:
    """Ermittelt den aktuellen Benutzerkontext für Mail-Filter in mehreren Pfaden."""
    source: object = {}
    try:
        state = vars(source_obj)
    except Exception:
        state = {}
    if isinstance(state, dict):
        for attr_name in MAIL_USER_CONTEXT_SOURCE_ATTRS:
            value = state.get(attr_name)
            if not value:
                continue
            source = value
            break

    if not source and isinstance(config_data, dict):
        fallback_email = str(config_data.get("current_email", "") or "").strip()
        if fallback_email:
            source = {"email": fallback_email}

    return {
        "username": _pick_from_source(source, "username", "user", "login_name"),
        "display_name": _pick_from_source(source, "display_name", "name", "full_name"),
        "role": _pick_from_source(source, "role", "user_role"),
        "place": _pick_from_source(source, "place", "ort", "location", "area"),
        "email": _pick_from_source(source, "email", "mail", "mail_address", "mailadresse"),
    }


def mail_group_matches_user(group: dict, context: dict[str, str]) -> bool:
    if not isinstance(group, dict):
        return False

    creator_values = [
        str(group.get(key, "") or "").strip().lower()
        for key in (
            "created_by",
            "creator",
            "owner",
            "username",
            "created_by_username",
            "created_by_name",
            "created_by_display_name",
            "ersteller",
        )
    ]
    place_values = [
        str(group.get(key, "") or "").strip().lower()
        for key in (
            "place",
            "ort",
            "location",
            "area",
            "region",
            "place_name",
        )
    ]
    creator_role = str(
        group.get("created_by_role")
        or group.get("creator_role")
        or group.get("owner_role")
        or ""
    ).strip().lower()

    current_username = context.get("username", "").strip().lower()
    current_name = context.get("display_name", "").strip().lower()
    current_place = context.get("place", "").strip().lower()
    current_role = context.get("role", "").strip().lower()

    if current_username and current_username in creator_values:
        return True
    if current_name and current_name in creator_values:
        return True
    if current_place and current_place in place_values:
        return True
    if creator_role in {"admin", "superadmin"} and current_role in {"admin", "superadmin"}:
        return True
    return False
