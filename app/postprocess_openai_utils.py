from __future__ import annotations


def openai_cached_model_result(item: dict, model: str, field: str) -> dict:
    results = item.get(field)
    if not isinstance(results, dict):
        return {}
    wanted = str(model or "").casefold()
    for stored_model, data in results.items():
        if str(stored_model or "").casefold() == wanted and isinstance(data, dict):
            return data
    return {}


def store_openai_model_result(item: dict, model: str, field: str, data: dict) -> None:
    model = str(model or "").strip()
    if not model:
        return
    results = item.get(field)
    if not isinstance(results, dict):
        results = {}
    results[model] = data
    item[field] = results


def openai_used_models(item: dict, field: str, legacy_model_field: str = "") -> list[str]:
    models: list[str] = []
    results = item.get(field)
    if isinstance(results, dict):
        models.extend(str(model).strip() for model in results.keys() if str(model).strip())
    if legacy_model_field:
        legacy = str(item.get(legacy_model_field) or "").strip()
        if legacy:
            models.append(legacy)
    return list(dict.fromkeys(models))
