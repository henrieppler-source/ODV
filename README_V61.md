# ODV v61 – Punkte/Bearbeiter-Feinschliff

Änderungen:

- Punkte bei Selbst-Löschung eigener punkteauslösender Eingaben werden wieder entfernt.
- Admin-Korrekturen löschen Punkte des ursprünglichen Bearbeiters nicht.
- Korrektur-/Ergänzungspunkt ab mehr als 10 Zeichen Änderung.
- „Mein Punktestand“ zeigt für Admins ein Auswahlfeld zur Einsicht fremder Punktekonten.
- Vorläufige Punkte für noch nicht übernommene Dokumente werden angezeigt.
- Doppelklick im Punktekonto öffnet das Dokument in „Dateien bearbeiten“.
- In „Dateien bearbeiten“ kann der Admin „Hochgeladen von“ per Auswahlfeld ändern.
- Bei Änderung des Hochladers werden vorhandene automatische Punkte des bisherigen Hochladers auf den neuen Hochlader übertragen.

Serverseitig `server/routes_v61.php` als `ortschronik-api/routes.php` hochladen. Keine SQL-Migration erforderlich, sofern v48/v49/v51/v55/v60 bereits eingespielt sind.
