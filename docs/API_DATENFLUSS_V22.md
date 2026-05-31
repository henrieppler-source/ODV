# v22 API-Datenfluss

Diese Version schließt den zentralen API-/MySQL-Datenfluss weiter:

- Dashboard lädt Dokumente primär aus MySQL über `GET /api/documents`.
- Doppelklick im Dashboard lädt Detaildaten über `GET /api/documents/{upload_id}`.
- Dateien bearbeiten lädt die Admin-Liste primär über `GET /api/documents`.
- Bei Auswahl eines Dokuments werden Personen und Historie über `GET /api/documents/{upload_id}` nachgeladen.
- Änderungen an Metadaten, Status, Dateiname und Pfad werden über `PUT /api/documents/{upload_id}` gespeichert.
- Personenzuordnungen werden über `PUT /api/documents/{upload_id}/persons` gespeichert.
- JSON-Dateien bleiben als lokale/Nextcloud-Sicherung erhalten.
- Falls die API nicht erreichbar ist, versucht die App weiterhin mit lokalen JSON-Sicherungen zu arbeiten.

## Optionaler API-Hinweis

Die App verhindert bereits, dass der angemeldete Superadmin sich selbst deaktiviert. Diese Regel sollte zusätzlich serverseitig in `PUT /api/users/{id}` abgesichert werden.

Im PUT-Block für Benutzer vor dem Speichern ergänzen:

```php
if ($userId === (int)$currentUser['id'] && $isActive !== 1) {
    json_response([
        'success' => false,
        'error' => 'Der aktuell angemeldete Benutzer kann sich nicht selbst deaktivieren'
    ], 400);
}
```
