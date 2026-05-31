# ODV v54 – Bearbeiter-Bearbeitung und UI-Aufräumung

Änderungen gegenüber v53:

- Normale Bearbeiter sehen den Reiter **Dateien bearbeiten** und können eigene, noch nicht übernommene Dokumente ergänzen.
- Für normale Bearbeiter heißt der Aktionsbereich **Aktionen**; Admin-/Superadmin-Funktionen bleiben ausgeblendet.
- Normale Bearbeiter dürfen Metadaten und Dateinamen eigener, noch nicht übernommener Dokumente ändern, aber weder Status noch Zielordner ändern.
- Sonderpunkte bleiben Admins/Superadmins vorbehalten.
- **Ausgewählte PDFs zusammenfassen...** ist oberhalb der Liste in der Status-Zeile positioniert.
- **Punkte für Bearbeitungsliste nachtragen...** wurde aus dem Aktionsbereich entfernt und liegt nur noch im Admin-Menü für Superadmins.
- Dokumenttyp ist in Upload und Bearbeitung als Auswahlfeld nutzbar; neue erkannte Dokumenttypen werden automatisch ergänzt.
- Serverroute v54 schützt zusätzlich, dass normale Bearbeiter übernommene Dokumente nicht bearbeiten und keine Dateien verschieben können.

Serverseitig:

1. `server/routes_v54.php` als neue `ortschronik-api/routes.php` hochladen.
2. Keine zusätzliche SQL-Migration erforderlich, wenn v48/v49/v51 bereits eingespielt sind.
