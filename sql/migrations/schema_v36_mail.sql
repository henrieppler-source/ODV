-- v36: E-Mail-Adressen und Rundmail-Verteiler
-- Import in phpMyAdmin nur einmal nötig. Falls users.email bereits existiert,
-- die ALTER-Zeile ggf. auskommentieren oder überspringen.

ALTER TABLE users
ADD COLUMN email VARCHAR(255) DEFAULT NULL AFTER display_name;

CREATE TABLE IF NOT EXISTS mail_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    description TEXT DEFAULT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    updated_by_user_id INT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_mail_groups_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mail_group_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_group_user (group_id, user_id),
    CONSTRAINT fk_mgm_group FOREIGN KEY (group_id) REFERENCES mail_groups(id) ON DELETE CASCADE,
    CONSTRAINT fk_mgm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT INTO mail_groups (name, description, is_active)
VALUES
('Alle Ortschronisten', 'Allgemeiner Verteiler für aktive Ortschronisten; Mitglieder können manuell gepflegt werden.', 1),
('Admins', 'Administratoren und Superadmins der Ortschronisten-Anwendung.', 1)
ON DUPLICATE KEY UPDATE
    description = VALUES(description),
    is_active = VALUES(is_active);
