# SQL-Ordner

## Struktur

- `current/`: Ausgangs- beziehungsweise aktuelle Basisschemata.
- `migrations/`: versionierte Schema- und Strukturmigrationen.
- `resets/`: Reset-Scripte fuer Bewegungs-/Testdaten. Diese Scripte koennen Daten loeschen und duerfen nur bewusst ausgefuehrt werden.
- `archive/`: ersetzte oder historische SQL-Dateien, die nicht mehr im normalen Ablauf verwendet werden.

## Migrationsregel

Wenn fuer eine neue ODV-Version Tabellen auf dem MySQL-Server angepasst werden muessen:

1. Vorher eine Server-/Datenbanksicherung erstellen.
2. Betroffene Tabelle vor der Aenderung kopieren.
3. Die Kopie mit der Version vor der Anpassung benennen, z. B. `documents_v104`, wenn die Migration auf v105 fuehrt.
4. Erst danach die Struktur der Originaltabelle anpassen.
5. Migration, Sicherungstabellen und Ergebnis in der Haupt-`README.md` unter `Versionshistorie` dokumentieren.

Beispiel:

```sql
CREATE TABLE documents_v104 LIKE documents;
INSERT INTO documents_v104 SELECT * FROM documents;

ALTER TABLE documents
  ADD COLUMN example_column VARCHAR(255) DEFAULT NULL;
```

Bei grossen Tabellen oder knappen Hosting-Limits vorher pruefen, ob die Kopie serverseitig sinnvoll moeglich ist.

## Ausfuehrung

Migrationen sollen bevorzugt ueber den Superadmin-Bereich von ODV ausgefuehrt werden:

```text
Admin > Datenbankmigrationen pruefen/ausfuehren...
```

Die API nutzt dafuer die serverseitige Datenbankverbindung. MySQL-Zugangsdaten muessen nicht im ODV-Client gespeichert werden.
