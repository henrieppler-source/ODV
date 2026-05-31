# V76 Änderungen

## Dateiansicht

Die Dateiansicht wurde für Bearbeiter/Admins nochmals korrigiert. Die Rechte- und Baumlogik erkennt ODV-Hauptordner jetzt auch dann, wenn diese nicht direkt im Nextcloud-Stammverzeichnis liegen, sondern z. B. unter `Ortschronisten_Gemeinsam`.

Damit soll `00_ORTSCHRONIK` bei Leserecht vollständig rekursiv angezeigt werden, einschließlich tiefer Strukturen wie `90_Archive_und_Quellen/90-10_Zeitungen/Freies_Wort/...`.

## Metadatenrechte

In „Dateien anzeigen“ gilt:

- Admin/Superadmin dürfen Metadaten bearbeiten.
- Bearbeiter dürfen Metadaten bearbeiten, wenn sie Schreibrecht auf den Ordner haben.
- Bearbeiter dürfen eigene bereits erfasste Dateien bearbeiten.
- Fehlt „Erfasst von“, ist Bearbeitung trotzdem erlaubt, wenn Schreibrecht auf dem Ordner besteht.

## Drag & Drop

Im Reiter „Dateien hochladen“ kann eine Datei aus dem Windows Explorer per Drag & Drop abgelegt werden. Dies wählt die Datei nur aus; der Upload startet weiterhin erst durch „Datei hochladen“.

## Technische Hinweise

Für Drag & Drop wird `tkinterdnd2` als optionale Abhängigkeit eingebunden. Fehlt die Bibliothek, läuft ODV weiter und zeigt im Upload-Reiter den Hinweis, dass Drag & Drop nicht verfügbar ist.
