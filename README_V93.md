# ODV Version v93

## OpenAI-Kosten, Ortsnamen und Formularfix

- Die OpenAI-Verbrauchsanzeige zeigt nun zusätzlich eine Kostenschätzung und freie Kontext-Tokens an, soweit das gewählte Modell bekannt ist.
- Unterstützte Preisprofile: `gpt-3.5-turbo`, `gpt-4o-mini`, `gpt-4o`.
- Die lokale/OpenAI-Metadatenableitung achtet besonders auf die Orte Bedheim, Eicha, Gleicherwiesen, Gleichamberg, Hindfeld, Milz, Mendhausen, Roth, Haina, Römhild, Sülzdorf, Westenfeld, Zeilfeld, Mönchshof und Simmershausen.
- Erkannte Orte werden im Feld `Ort` ergänzt, ohne vorhandene Orte zu überschreiben.
- Die überlappenden Felder in Schritt 2 `Quelle / Rechte / Transkription` wurden korrigiert.

Geänderte Dateien:

- `app/upload_tab.py`
- `app/openai_client.py`
- `app/upload_wizard.py`
- `app/main.py`
