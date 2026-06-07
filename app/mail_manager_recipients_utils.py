from __future__ import annotations

from typing import Callable


def _dedupe_emails(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = str(item or "").strip()
        if not key:
            continue
        lower = key.lower()
        if lower in seen:
            continue
        seen.add(lower)
        out.append(key)
    return out


def collect_mail_recipients(
    users: list[dict],
    user_list: object,
    groups: list[dict],
    group_listbox: object,
    manual_recipients: str,
) -> list[str]:
    emails: list[str] = []

    if user_list is not None:
        for idx in user_list.curselection():
            try:
                user = users[int(idx)]
            except Exception:
                continue
            email = str(user.get("email", "") or "").strip()
            if email:
                emails.append(email)

    selected_indices: set[int] = set(group_listbox.curselection() if group_listbox is not None else [])
    for idx, group in enumerate(groups):
        if idx not in selected_indices:
            continue
        for member in list(group.get("members", []) or []) + list(group.get("external_members", []) or []):
            email = str(member.get("email", "") or "").strip()
            if email:
                emails.append(email)

    for part in str(manual_recipients or "").replace(",", ";").split(";"):
        email = part.strip()
        if email:
            emails.append(email)

    return _dedupe_emails(emails)


def build_mail_attachments(file_paths: list[str], attachment_builder: Callable[[str], dict | None]) -> list[dict]:
    attachments: list[dict] = []
    total_size = 0
    for file_path in file_paths:
        item = attachment_builder(file_path)
        if not item:
            continue
        attachments.append(item)
        total_size += int(item.get("size", 0) or 0)
    if not attachments:
        raise ValueError("Es wurde keine gültige Anlage gefunden.")
    if total_size > 12 * 1024 * 1024:
        raise ValueError("Die Anlagen sind zusammen größer als 12 MB. Bitte besser als Nextcloud-Link versenden.")
    return attachments
