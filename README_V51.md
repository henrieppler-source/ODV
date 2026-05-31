# ODV v51 – Metadaten- und Sonderpunkte-Feinschliff

## Neu

- **Transkription erstellt** ist jetzt ein Kontrollkästchen.
- **Transkriptionsart** ist eine schmale Auswahlliste mit:
  - kurze Transkription
  - vollständige Transkription
  - schwierige Handschrift
  - Zeitung / Akte / Urkunde
- **Rechte / Nutzung allgemein** ist eine schmale Auswahlliste mit:
  - A – frei nutzbar mit Namensnennung
  - B – Nutzung nur nach Rücksprache
  - C – nur interne Recherche - nicht veröffentlichen
  - D – Rechte unklar
- **Stichwörter** sollen durch Komma oder Semikolon getrennt werden, z. B. `Schule, Lehrer, Kirmes`.
- **Sonderpunkte** können im Dialog aus verwaltbaren Punkteregeln gewählt werden. Die Punktzahl kann bewusst überschrieben werden; eine Begründung ist Pflicht.

## Server

Bitte `sql/schema_v51_point_rules_ui.sql` in phpMyAdmin importieren. Dadurch werden die Standard-Sonderpunkte-Regeln für das aktuelle Kalenderjahr ergänzt.

`server/routes_v51.php` entspricht funktional v50 und ist beigefügt, damit die Versionsdateien zusammenpassen.
