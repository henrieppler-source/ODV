-- ODV v83: optionale Nextcloud-Zugangsdaten pro Benutzer vorbereiten
-- Fuegt verschlüsselbar gespeicherte Nextcloud-Zugangsdaten zur zentralen Benutzertabelle hinzu.

ALTER TABLE users
    ADD COLUMN nextcloud_username VARCHAR(255) NULL AFTER email,
    ADD COLUMN nextcloud_password_enc TEXT NULL AFTER nextcloud_username;
