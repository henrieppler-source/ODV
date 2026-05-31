-- ODV v79: Menüstruktur, manuelle Sonderpunkte mit Zeitaufwand
-- Vor Import bitte Datenbank sichern.

CREATE TABLE IF NOT EXISTS manual_special_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_display_name VARCHAR(200) NOT NULL,
    points_year INT NOT NULL,
    activity_date DATE DEFAULT NULL,
    rule_key VARCHAR(120) NOT NULL,
    rule_label VARCHAR(255) NOT NULL,
    hours DECIMAL(8,2) DEFAULT NULL,
    points INT NOT NULL,
    reason TEXT NOT NULL,
    note TEXT DEFAULT NULL,
    created_by_user_id INT DEFAULT NULL,
    created_by_name VARCHAR(200) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_msp_year (points_year),
    INDEX idx_msp_user_year (user_id, points_year),
    INDEX idx_msp_created_by (created_by_user_id),
    CONSTRAINT fk_msp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_msp_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS system_settings (
    setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
    setting_value TEXT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO system_settings (setting_key, setting_value)
VALUES ('manual_points_per_hour', '150')
ON DUPLICATE KEY UPDATE setting_value = setting_value;

INSERT INTO point_rules (year, rule_key, label, category, points, is_active)
VALUES
(YEAR(CURDATE()), 'manual_archive_research', 'Recherche in Archiven', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_collection_indexing', 'Erschließung von Beständen', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_event_organization', 'Organisation Veranstaltung', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_excursion_organization', 'Organisation Busfahrt / Exkursion', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_exhibition_work', 'Mitarbeit an Ausstellung', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_digitization_support', 'Digitalisierungshilfe', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_lecture_guided_tour', 'Vortrag / Führung', 'manual', 0, 1),
(YEAR(CURDATE()), 'manual_other', 'Sonstige Tätigkeit', 'manual', 0, 1)
ON DUPLICATE KEY UPDATE
    label = VALUES(label),
    category = VALUES(category),
    is_active = VALUES(is_active);
