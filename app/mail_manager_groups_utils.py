from __future__ import annotations

from typing import Any


def group_display_label(group: dict) -> str:
    status = "" if int(group.get("is_active", 1) or 0) == 1 else " (inaktiv)"
    return f"{group.get('name', '')}{status}"


def parse_external_members_text(text: str) -> list[dict]:
    result: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) >= 3:
            first, last, email = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            first, last, email = "", parts[0], parts[1]
        else:
            first, last, email = "", "", parts[0]
        if email:
            result.append({"first_name": first, "last_name": last, "email": email, "is_active": True})
    return result


def render_external_members_text(members: list[dict]) -> str:
    lines: list[str] = []
    for member in members or []:
        lines.append(f"{member.get('first_name', '')}; {member.get('last_name', '')}; {member.get('email', '')}")
    return "\n".join(lines)


def selected_member_ids(group: dict) -> set[int]:
    members: set[int] = set()
    for member in group.get("members", []):
        if not isinstance(member, dict):
            continue
        for key in ("user_id", "id", "uid", "userId"):
            try:
                uid = int(member.get(key, 0) or 0)
            except Exception:
                uid = 0
            if uid > 0:
                members.add(uid)
                break
    return members


def build_mail_group_payload(
    gid: int,
    name: str,
    description: str,
    is_active: bool,
    member_ids: list[int],
    external_members: list[dict],
) -> dict[str, Any]:
    return {
        "id": int(gid or 0),
        "name": str(name).strip(),
        "description": str(description).strip(),
        "is_active": bool(is_active),
        "member_user_ids": [int(uid) for uid in member_ids if int(uid) > 0],
        "external_members": external_members,
    }
