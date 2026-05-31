# ODV v59 – Punkte-Schwellen für Beschreibung und Stichwörter

Änderungen gegenüber v58:

- Punkte für „Aussagekräftige Beschreibung“ werden erst ab 50 Zeichen vergeben.
- Beim Feld „Beschreibung“ wird live ein Zeichenzähler angezeigt.
- Punkte für „Stichwörter“ werden erst ab mindestens 3 Stichwörtern vergeben.
- Stichwörter werden durch Komma oder Semikolon getrennt.
- Hinweise stehen direkt unter den passenden Feldern.
- Die Regeln gelten sowohl bei neuer Punktevergabe als auch bei der Punkte-Nachberechnung.

Serverseitig:

- `server/routes_v59.php` als `ortschronik-api/routes.php` hochladen.
- Keine neue SQL-Migration nötig.
