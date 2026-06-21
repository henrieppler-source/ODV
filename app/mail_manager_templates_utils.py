from __future__ import annotations


def get_mail_text_templates(config_data: dict) -> list[dict]:
    templates = config_data.get("mail_text_templates", [])
    if not isinstance(templates, list):
        return []
    out: list[dict] = []
    for item in templates:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "") or item.get("name", "") or "").strip()
        text = str(item.get("text", "") or "").strip()
        if label and text:
            out.append({"label": label, "text": text})
    return out


def set_mail_text_templates(config_data: dict, templates: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for item in templates or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "") or item.get("name", "") or "").strip()
        text = str(item.get("text", "") or "").rstrip()
        if label and text:
            cleaned.append({"label": label, "text": text})
    config_data["mail_text_templates"] = cleaned
    return cleaned


def template_labels(templates: list[dict]) -> list[str]:
    return [str(item.get("label", "") or "").strip() for item in templates if str(item.get("label", "") or "").strip()]
