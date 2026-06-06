from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


class OpenAIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, response: Any = None):
        super().__init__(message)
        self.status = status
        self.response = response

    def user_message(self) -> str:
        message = str(self)
        if isinstance(self.response, dict):
            error = self.response.get("error")
            if isinstance(error, dict):
                error_type = error.get("type")
                error_message = error.get("message")
                if error_type == "insufficient_quota" or error_message and "quota" in str(error_message).lower():
                    return "OpenAI-Kontingent erschöpft. Bitte Plan/Guthaben prüfen."
                if error_message:
                    return str(error_message)
                if error_type:
                    return str(error_type)
            if isinstance(error, str):
                if "insufficient_quota" in error or "quota" in error.lower():
                    return "OpenAI-Kontingent erschöpft. Bitte Plan/Guthaben prüfen."
                return error
            response_message = self.response.get("message")
            if isinstance(response_message, str):
                if "insufficient_quota" in response_message or "quota" in response_message.lower():
                    return "OpenAI-Kontingent erschöpft. Bitte Plan/Guthaben prüfen."
                return response_message
        if "insufficient_quota" in message.lower() or "quota" in message.lower():
            return "OpenAI-Kontingent erschöpft. Bitte Plan/Guthaben prüfen."
        return message


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key.strip()
        self.model = model.strip() or "gpt-3.5-turbo"
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, data: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
        if not self.api_key:
            raise OpenAIError("OpenAI API-Schlüssel fehlt")
        url = self.base_url + (path if path.startswith("/") else "/" + path)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw}
            message = payload.get("error") or payload.get("message") or f"HTTP-Fehler {exc.code}"
            raise OpenAIError(message, status=exc.code, response=payload) from exc
        except urllib.error.URLError as exc:
            raise OpenAIError(f"OpenAI nicht erreichbar: {exc.reason}") from exc
        except TimeoutError as exc:
            raise OpenAIError("OpenAI-Zeitüberschreitung") from exc
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise OpenAIError("OpenAI-Antwort ist kein gültiges JSON") from exc
        if not isinstance(payload, dict):
            raise OpenAIError("OpenAI-Antwort hat unerwartetes Format")
        return payload

    def parse_json_content(self, content: str) -> dict[str, Any]:
        text = str(content or "").strip()
        if not text:
            raise OpenAIError("OpenAI-Antwort ist leer")
        candidates = [text]
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            candidates.append(fenced.group(1).strip())
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidates.append(text[start:end + 1])
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                result = json.loads(candidate)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError as exc:
                last_error = exc
        raise OpenAIError("OpenAI-Antwort konnte nicht als JSON gelesen werden") from last_error


    def analyze_upload_file(self, filename: str, extension: str, sample: str | None = None) -> dict[str, Any]:
        """Kombinierte OpenAI-Prüfung für Upload-Dateien.

        Ein Button-Klick erzeugt genau einen API-Aufruf und liefert sowohl
        die Kurzbewertung als auch direkt übernehmbare Metadatenvorschläge.
        """
        prompt = (
            "Du bist ein Assistent für eine historische Archiv-Uploader-Anwendung. "
            "Bewerte das hochgeladene Dokument anhand von Dateiname, Dateiendung und vor allem der Textprobe "
            "und schlage zugleich Metadaten vor. Nutze erkennbare Angaben wie Überschrift, Ort:, Zeit/Dauer:, Datum, Tagesordnung und Themen. "
            "Achte besonders auf diese Ortsnamen und übernimm alle vorkommenden passenden Orte in metadata.place, kommasepariert: "
            "Bedheim, Eicha, Gleicherwiesen, Gleichamberg, Hindfeld, Milz, Mendhausen, Roth, Haina, Römhild, Sülzdorf, Westenfeld, Zeilfeld, Mönchshof, Simmershausen. "
            "Zusätzliche eindeutig erkennbare Orte dürfen ebenfalls ergänzt werden. "
            "Bei Protokollen/Niederschriften sollen Datum/Zeitraum, Ort, Anlass/Ereignis, Stichwörter und Beschreibung abgeleitet werden, wenn sie im Text stehen. "
            "Antworte ausschließlich mit gültigem JSON und ohne Zusatztext. "
            "Nutze exakt dieses Format: "
            "{\"file_type\": \"<Kurztyp>\", \"confidence\": \"<niedrig/mittel/hoch>\", "
            "\"advice\": \"<kurzer Hinweis>\", "
            "\"metadata\": {\"document_type\": \"...\", \"document_date\": \"...\", "
            "\"event\": \"...\", \"place\": \"...\", \"keywords\": \"...\", "
            "\"primary_source\": \"...\", \"secondary_source\": \"...\", \"description\": \"...\"}}. "
            "Wenn ein Wert nicht verlässlich ableitbar ist, verwende einen leeren String."
        )
        if sample:
            sample = sample.strip()[:4000]
            prompt += f"\nDateiinhalt (Auszug): {sample}"
        prompt += f"\nDateiname: {filename}\nDateiendung: {extension or '(keine)'}"

        response = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Bitte die JSON-Antwort wie oben liefern."},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 700,
            },
        )
        if "choices" not in response or not response["choices"]:
            raise OpenAIError("OpenAI-Antwort enthält keine Auswahl")
        content = response["choices"][0].get("message", {}).get("content", "")
        result = self.parse_json_content(content)
        if not isinstance(result, dict):
            raise OpenAIError("OpenAI-Antwort hat unerwartetes Format")
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            result["metadata"] = {}
        result["usage"] = response.get("usage", {})
        return result

    def analyze_place_contexts(self, filename: str, contexts: list[dict[str, str]], fallback_text: str | None = None, max_context_chars: int = 1200) -> dict[str, Any]:
        """Erstellt eine ortsbezogene Inhaltszusammenfassung aus lokalen Fundstellen."""
        clean_contexts = []
        max_context_chars = max(300, min(15000, int(max_context_chars or 1200)))
        for context in contexts:
            place = str(context.get("place", "") or "").strip()
            text = str(context.get("text", "") or "").strip()
            if place and text:
                clean_contexts.append({"place": place, "text": text[:max_context_chars]})
        fallback = str(fallback_text or "").strip()
        if not clean_contexts and not fallback:
            raise OpenAIError("Keine Ortsfundstellen oder Textprobe für OpenAI vorhanden")
        prompt = (
            "Du bist ein Assistent für eine historische Ortschronik. "
            "Du erhältst entweder Textausschnitte, in denen Orte aus der Ortsverwaltung vorkommen, oder eine begrenzte Textprobe, falls lokal kein Ort gefunden wurde. "
            "Erstelle daraus eine sachliche Inhaltszusammenfassung und passende Stichwörter. "
            "Wenn Orte erkennbar sind, liste sie in places und place_summaries auf. "
            "Erfinde keine Angaben, die nicht in den Ausschnitten stehen. "
            "Antworte ausschließlich mit gültigem JSON im Format: "
            "{\"summary\":\"...\", \"keywords\":\"...\", \"places\":\"...\", "
            "\"document_date\":\"...\", \"event\":\"...\", \"primary_source\":\"...\", "
            "\"place_summaries\":[{\"place\":\"...\", \"summary\":\"...\"}]}. "
            "Die Stichwörter sollen kommasepariert sein. "
            "document_date, event und primary_source nur füllen, wenn sie aus dem Text ableitbar sind."
        )
        response = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps({"filename": filename, "contexts": clean_contexts, "fallback_text": fallback[:4000]}, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 1000,
            },
        )
        if "choices" not in response or not response["choices"]:
            raise OpenAIError("OpenAI-Antwort enthält keine Auswahl")
        content = response["choices"][0].get("message", {}).get("content", "")
        result = self.parse_json_content(content)
        result["usage"] = response.get("usage", {})
        return result

    def classify_file(self, filename: str, extension: str, sample: str | None = None) -> dict[str, str]:
        prompt = (
            "Du bist ein Assistent für eine historische Archiv-Uploader-Anwendung. "
            "Bewerte das hochgeladene Dokument nur anhand des Dateinamens, der Dateiendung und einer optionalen kurzen Textprobe. "
            "Antworte nur mit gültigem JSON in folgendem Format: {\"file_type\": \"<Kurztyp>\", \"confidence\": \"<niedrig/mittel/hoch>\", \"advice\": \"<kurzer Hinweis>\"}. "
            "Füge keinen zusätzlichen Text hinzu."
        )
        if sample:
            sample = sample.strip()[:1200]
            prompt += f"\nDateiinhalt (Auszug): {sample}"
        prompt += f"\nDateiname: {filename}\nDateiendung: {extension or '(keine)'}"

        response = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Bitte die JSON-Antwort wie oben liefern."},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 180,
            },
        )
        if "choices" not in response or not response["choices"]:
            raise OpenAIError("OpenAI-Antwort enthält keine Auswahl")
        content = response["choices"][0].get("message", {}).get("content", "")
        result = self.parse_json_content(content)
        result["usage"] = response.get("usage", {})
        return result

    def get_balance(self) -> dict[str, Any]:
        response = self.request("/dashboard/billing/credit_grants", data=None, method="GET")
        if "total_available" in response:
            return {
                "available": response["total_available"],
                "is_paid_subscription": response.get("is_paid_subscription", False),
                "granted_amount": response.get("granted_amount"),
                "used_amount": response.get("used_amount"),
            }
        if "error" in response:
            raise OpenAIError(response["error"])
        raise OpenAIError("OpenAI-Billing-Antwort enthält kein Guthabenfeld")

    def suggest_metadata(self, filename: str, extension: str, sample: str | None = None) -> dict[str, Any]:
        prompt = (
            "Du bist ein Assistent für eine historische Archiv-Uploader-Anwendung. "
            "Basierend auf Dateiname, Dateiendung und einer optionalen kurzen Textprobe schlage bitte Metadaten in JSON vor. "
            "Antworte nur mit gültigem JSON und ohne zusätzlichen Text. "
            "Nutze dieses Format: {\"document_type\": \"...\", \"document_date\": \"...\", \"event\": \"...\", \"place\": \"...\", \"keywords\": \"...\", \"primary_source\": \"...\", \"secondary_source\": \"...\", \"description\": \"...\"}. "
        )
        if sample:
            sample = sample.strip()[:1200]
            prompt += f"\nDateiinhalte (Auszug): {sample}"
        prompt += f"\nDateiname: {filename}\nDateiendung: {extension or '(keine)'}"

        response = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Bitte die JSON-Antwort wie oben liefern."},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 260,
            },
        )
        if "choices" not in response or not response["choices"]:
            raise OpenAIError("OpenAI-Antwort enthält keine Auswahl")
        content = response["choices"][0].get("message", {}).get("content", "")
        result = self.parse_json_content(content)
        result["usage"] = response.get("usage", {})
        return result

    def verify_key(self) -> bool:
        response = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Du bist ein Testassistent."},
                    {"role": "user", "content": "Bitte bestätige, dass der Schlüssel gültig ist."},
                ],
                "temperature": 0.0,
                "max_tokens": 1,
            },
        )
        if "choices" not in response or not response["choices"]:
            raise OpenAIError("OpenAI-Antwort enthält keine Auswahl")
        return True
