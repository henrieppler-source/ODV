-- Entwurf für die zentrale MySQL/MariaDB-Datenbank
-- Stand: MVP-Grundlage

CREATE TABLE users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NULL,
    nextcloud_username VARCHAR(255) NULL,
    nextcloud_password_enc TEXT NULL,
    role ENUM('ortschronist', 'admin', 'superadmin') NOT NULL DEFAULT 'ortschronist',
    place VARCHAR(200) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME NULL,
    last_seen_history_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE areas (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    nextcloud_path VARCHAR(1000) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_area_permissions (
    user_id BIGINT UNSIGNED NOT NULL,
    area_id BIGINT UNSIGNED NOT NULL,
    can_read TINYINT(1) NOT NULL DEFAULT 1,
    can_upload TINYINT(1) NOT NULL DEFAULT 0,
    can_admin TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, area_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (area_id) REFERENCES areas(id)
);

CREATE TABLE documents (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    upload_id VARCHAR(80) NOT NULL UNIQUE,
    original_filename VARCHAR(500) NOT NULL,
    current_filename VARCHAR(500) NOT NULL,
    original_path VARCHAR(1000) NULL,
    current_path VARCHAR(1000) NOT NULL,
    area_id BIGINT UNSIGNED NULL,
    uploaded_by_user_id BIGINT UNSIGNED NULL,
    uploaded_by_display_name VARCHAR(200) NOT NULL,
    uploaded_at DATETIME NOT NULL,
    status ENUM('hochgeladen', 'erfasst', 'geaendert', 'rueckfrage', 'geprueft', 'archiviert') NOT NULL DEFAULT 'hochgeladen',
    source VARCHAR(500) NULL,
    original_location VARCHAR(500) NULL,
    document_date VARCHAR(100) NULL,
    event VARCHAR(300) NULL,
    place VARCHAR(300) NULL,
    document_type VARCHAR(100) NULL,
    description TEXT NULL,
    rights_note TEXT NULL,
    copyright_author VARCHAR(500) NULL,
    rights_holder VARCHAR(500) NULL,
    usage_permission VARCHAR(500) NULL,
    license_note TEXT NULL,
    archive_name VARCHAR(500) NULL,
    archive_signature VARCHAR(500) NULL,
    archive_accessed_at VARCHAR(100) NULL,
    note TEXT NULL,
    person_status ENUM('none', 'not_identified', 'identified') NOT NULL DEFAULT 'none',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (area_id) REFERENCES areas(id),
    FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
);

CREATE TABLE document_person_marks (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT UNSIGNED NOT NULL,
    number_on_photo INT NOT NULL,
    x DECIMAL(8,6) NOT NULL,
    y DECIMAL(8,6) NOT NULL,
    display_name VARCHAR(300) NULL,
    certainty ENUM('sicher', 'vermutlich', 'unbekannt') NOT NULL DEFAULT 'unbekannt',
    note TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_by_display_name VARCHAR(200) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE document_history (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT UNSIGNED NULL,
    upload_id VARCHAR(80) NULL,
    user_id BIGINT UNSIGNED NULL,
    user_display_name VARCHAR(200) NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    details TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_history_created_at (created_at),
    INDEX idx_history_upload_id (upload_id)
);
