# v29 Produktiv-Härtung

Umgesetzt aus Block 1 „Technik härten“:

- App schreibt lokales Log nach `%USERPROFILE%\.ortschronik_uploader\logs\app.log`.
- Technische Fehler mit Traceback werden nach `app_trace.log` geschrieben.
- Statuszeile in der Anwendung zeigt API- und Nextcloud-Stammverzeichnis-Status.
- Reiterwechsel prüft den Verbindungsstatus automatisch.
- Zielordnerprüfung wird protokolliert.
- API enthält Login-Rate-Limiting über `api_login_attempts`.
- `/api/db-test` bleibt nur mit Superadmin-Token nutzbar.
- Uploads und Dokumentupdates prüfen serverseitig Schreibrechte nach Ordnergruppen.
- Dokumentlisten für Ortschronisten werden serverseitig anhand Leserechten gefiltert.

Bereits erledigt: Ortsordner-Stammdatentabelle aus v27.

Nächster empfohlener Block: Bedienung stabilisieren – Ersteinrichtungsdialog, Pflichtfelder, Statuswerte endgültig normieren.
