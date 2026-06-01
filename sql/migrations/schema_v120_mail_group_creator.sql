-- v120: Mail-Verteiler-Erstellerinformationen
-- Ergänzt die Verteiler um Creator-Felder für Sichtbarkeit und Nachvollziehbarkeit.

ALTER TABLE mail_groups
    ADD COLUMN IF NOT EXISTS created_by_user_id INT DEFAULT NULL AFTER is_active,
    ADD COLUMN IF NOT EXISTS created_by_display_name VARCHAR(200) DEFAULT NULL AFTER created_by_user_id,
    ADD COLUMN IF NOT EXISTS created_by_role VARCHAR(40) DEFAULT NULL AFTER created_by_display_name,
    ADD COLUMN IF NOT EXISTS created_by_place VARCHAR(200) DEFAULT NULL AFTER created_by_role;

ALTER TABLE mail_groups
    ADD INDEX idx_mail_groups_creator (created_by_user_id),
    ADD INDEX idx_mail_groups_creator_place (created_by_place);
