-- ODV v79 - UI, Quellen, Suche, Verteiler, Punkteregeln
-- Ergänzt externe Verteilerempfänger und unterstützt neue Quellen-Metadatenfelder.

CREATE TABLE IF NOT EXISTS mail_group_external_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    first_name VARCHAR(255) DEFAULT NULL,
    last_name VARCHAR(255) DEFAULT NULL,
    email VARCHAR(255) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_mgem_group (group_id),
    INDEX idx_mgem_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Hinweis: Primärquelle/Sekundärquelle werden kompatibel im JSON-Metadatenfeld gespeichert
-- (primary_source/secondary_source sowie primaerquelle/sekundaerquelle).
