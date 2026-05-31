-- ODV v48: Beitrags- und Punkteverwaltung
-- Vor dem Import bitte Datenbank sichern.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS keywords TEXT DEFAULT NULL AFTER note,
    ADD COLUMN IF NOT EXISTS transcription_done TINYINT(1) NOT NULL DEFAULT 0 AFTER keywords,
    ADD COLUMN IF NOT EXISTS transcription_type VARCHAR(100) DEFAULT NULL AFTER transcription_done,
    ADD COLUMN IF NOT EXISTS transcription_note TEXT DEFAULT NULL AFTER transcription_type;

CREATE TABLE IF NOT EXISTS point_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    year INT NOT NULL,
    rule_key VARCHAR(100) NOT NULL,
    label VARCHAR(255) NOT NULL,
    category VARCHAR(80) NOT NULL DEFAULT 'metadata',
    points INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    updated_by_user_id INT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_point_rule_year_key (year, rule_key),
    CONSTRAINT fk_point_rules_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contribution_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    upload_id VARCHAR(100) NOT NULL,
    user_id INT NOT NULL,
    user_display_name VARCHAR(200) NOT NULL,
    points_year INT NOT NULL,
    category VARCHAR(80) NOT NULL,
    rule_key VARCHAR(120) NOT NULL,
    reason TEXT NOT NULL,
    source_field VARCHAR(120) DEFAULT NULL,
    points INT NOT NULL,
    created_by_user_id INT DEFAULT NULL,
    created_by_name VARCHAR(200) DEFAULT NULL,
    is_manual TINYINT(1) NOT NULL DEFAULT 0,
    is_confirmed TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_auto_point (document_id, user_id, rule_key, source_field, is_manual),
    INDEX idx_points_year (points_year),
    INDEX idx_points_user_year (user_id, points_year),
    INDEX idx_points_upload (upload_id),
    CONSTRAINT fk_points_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_points_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_points_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS point_year_closures (
    year INT PRIMARY KEY,
    closed_at DATETIME DEFAULT NULL,
    closed_by_user_id INT DEFAULT NULL,
    note TEXT DEFAULT NULL,
    CONSTRAINT fk_point_year_closed_by FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT INTO point_rules (year, rule_key, label, category, points, is_active)
VALUES
(YEAR(CURDATE()), 'metadata_description', 'Aussagekräftige Beschreibung', 'metadata', 2, 1),
(YEAR(CURDATE()), 'metadata_keywords', 'Stichwörter vergeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'metadata_source', 'Quelle/Herkunft angegeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'rights_usage_permission', 'Nutzungsfreigabe geklärt', 'metadata', 3, 1),
(YEAR(CURDATE()), 'rights_note', 'Rechtehinweis angegeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'rights_author', 'Urheber angegeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'rights_holder', 'Rechteinhaber angegeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'archive_name', 'Archiv/Bestand angegeben', 'metadata', 1, 1),
(YEAR(CURDATE()), 'archive_signature', 'Archivsignatur angegeben', 'metadata', 2, 1),
(YEAR(CURDATE()), 'document_date', 'Datum/Zeitraum angegeben', 'metadata', 1, 1),
(YEAR(CURDATE()), 'event_topic', 'Ereignis/Thema zugeordnet', 'metadata', 1, 1),
(YEAR(CURDATE()), 'persons_marked', 'Personen markiert', 'persons', 1, 1),
(YEAR(CURDATE()), 'persons_named', 'Personen mit Namen versehen', 'persons', 2, 1),
(YEAR(CURDATE()), 'transcription_short', 'Kurze Transkription / Auszug', 'metadata', 3, 1),
(YEAR(CURDATE()), 'transcription_full', 'Vollständige Transkription', 'metadata', 5, 1),
(YEAR(CURDATE()), 'transcription_difficult', 'Schwierige Handschrift / alte Schrift', 'metadata', 8, 1),
(YEAR(CURDATE()), 'admin_review_accepted', 'Dokument geprüft und übernommen', 'admin_review', 1, 1),
(YEAR(CURDATE()), 'admin_file_organization', 'Datei umbenannt oder verschoben', 'admin_review', 1, 1)
ON DUPLICATE KEY UPDATE
    label = VALUES(label),
    category = VALUES(category),
    points = VALUES(points),
    is_active = VALUES(is_active);
