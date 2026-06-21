from __future__ import annotations

import json
from typing import Any


def summarize_mail_history_documents(docs: object) -> str:
    if isinstance(docs, str):
        try:
            docs = json.loads(docs)
        except Exception:
            return docs
    if isinstance(docs, (list, tuple)):
        parts: list[str] = []
        for item in docs:
            if isinstance(item, dict):
                label = str(item.get("file") or item.get("filename") or item.get("name") or "").strip()
                link = str(item.get("link") or item.get("download_url") or item.get("url") or "").strip()
                expires_at = str(item.get("expires_at") or item.get("share_expires_at") or "").strip()
                text = label or link or str(item)
                if link and label:
                    text = label
                if expires_at:
                    text += f" (bis {expires_at})"
                parts.append(text)
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(docs or "")


def format_mail_history_detail(item: dict) -> str:
    """Lesbare Detailansicht für Versandhistorie statt Roh-JSON."""
    docs = item.get("documents") or item.get("links") or item.get("document_links") or ""
    if isinstance(docs, str):
        try:
            parsed = json.loads(docs)
            docs = parsed
        except Exception:
            pass
    lines = [
        "Versanddetails",
        "---------------",
        f"Zeitpunkt: {item.get('sent_at') or item.get('created_at') or ''}",
        f"Versendet von: {item.get('sender_name') or item.get('sent_by_name') or ''}",
        f"Empfänger: {item.get('recipient_email') or item.get('recipient') or ''}",
        f"Betreff: {item.get('subject') or ''}",
        f"Versandart: {item.get('mode') or item.get('send_mode') or ''}",
        f"Status: {item.get('status') or ''}",
        "",
        "Mailtext",
        "--------",
        str(item.get("body_preview") or item.get("body") or item.get("message") or "").replace("\\n", "\n"),
        "",
        "Dokumente / Links",
        "-----------------",
    ]
    if isinstance(docs, (list, tuple)):
        for i, d in enumerate(docs, 1):
            if isinstance(d, dict):
                label = d.get("file") or d.get("filename") or d.get("name") or ""
                link = d.get("link") or d.get("download_url") or d.get("url") or ""
                expires_at = d.get("expires_at") or d.get("share_expires_at") or ""
                lines.append(f"{i}. Datei: {label}")
                if link:
                    lines.append(f"   Link: {link}")
                if expires_at:
                    lines.append(f"   Gültig bis: {expires_at}")
            else:
                lines.append(f"{i}. {d}")
    elif docs:
        lines.append(str(docs))
    else:
        lines.append("Keine Dokumente/Links gespeichert.")
    if item.get("error") or item.get("error_message"):
        lines += ["", "Fehlerstatus", "------------", str(item.get("error") or item.get("error_message"))]
    return "\n".join(lines)


def load_mail_history_rows(api: Any, token: str, limit: int = 500) -> list[dict]:
    response = api.mail_history(token, limit=limit)
    return list(response.get("items", []) or response.get("history", []) or [])
