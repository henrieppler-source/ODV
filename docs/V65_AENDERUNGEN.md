# ODV v65 – Erfasste Bestandsdateien, Rundmail ohne Anlage, Layout

## Bestandsdateien

Physisch vorhandene Dateien ohne ODV-Metadaten bleiben reine Dateianzeige, bis tatsächlich Metadaten gespeichert werden. Erst dann wird ein JSON-/API-/MySQL-Datensatz erzeugt.

Neue Metadatensätze aus Bestandsdateien erhalten den Status `erfasst` und den Capture-Modus `existing_file_metadata`.

## Admin-Bearbeitungsliste

Bestandsdateien mit nachträglich erfassten Metadaten erscheinen nur in „Dateien bearbeiten“, wenn sie in den relevanten ODV-Hauptbereichen liegen. Admin-erfasste Bestandsdateien werden dort nicht erneut als Bearbeitungsfall angezeigt.

## Rundmail

Die Rundmail hat nun die Versandart „Keine Anlage“ als Standard. Link- und Anhangprüfungen greifen nur noch bei den entsprechenden Versandarten.

## Oberfläche

„Hochgeladen von“ wurde im Metadatenkontext zu „Erfasst von“. Der Rechte-Block wurde optisch auf die Höhe von „Zeit / Ort / Inhalt“ gesetzt.
