# ODV v49 – Punkte nur für zentrale Arbeitsordner

Diese Version ergänzt v48 um eine fachliche Einschränkung der Punktevergabe. Punkte werden nur noch für Dokumente vergeben, die ursprünglich in einen der zentralen Arbeits-/Ablagebereiche hochgeladen wurden:

- `01_ABLAGE_ORTSCHRONIK`
- `06_UNSERE_ARBEITEN`
- kompatibel zusätzlich: `06_ARBEIT_DER_ORTSCHRONISTEN` / `06_ARBEITEN_DER_ORTSCHRONISTEN`

Für Uploads in den eigenen Ortsordner werden keine Punkte vergeben. Die Dateien und Metadaten bleiben natürlich normal nutzbar; nur die Beitragsbewertung bleibt dafür aus.

## Einspielen serverseitig

1. `sql/schema_v48_points.sql` einspielen, falls v48 noch nicht eingespielt wurde.
2. Danach `sql/schema_v49_points_folder_scope.sql` einspielen.
3. `server/routes_v49.php` als neue `ortschronik-api/routes.php` hochladen.

## Wirkung

Beim Anlegen eines Dokuments wird `documents.points_eligible` gespeichert. Dadurch bleibt die Punkteberechtigung erhalten, auch wenn ein Admin die Datei später in `00_ORTSCHRONIK` verschiebt. Bereits vorhandene Dokumente werden anhand von `target_folder` und `current_path` nachklassifiziert.
