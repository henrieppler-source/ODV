-- ODV v74: Sitzungen, Geräte und Dokument-Bearbeitungssperren

CREATE TABLE IF NOT EXISTS odv_user_devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    device_id VARCHAR(128) NOT NULL,
    device_name VARCHAR(255) DEFAULT NULL,
    windows_user VARCHAR(255) DEFAULT NULL,
    os_name VARCHAR(128) DEFAULT NULL,
    os_version VARCHAR(255) DEFAULT NULL,
    app_version VARCHAR(32) DEFAULT NULL,
    first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT NULL,
    last_login_at DATETIME DEFAULT NULL,
    last_ip VARCHAR(64) DEFAULT NULL,
    is_blocked TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_user_device (user_id, device_id),
    INDEX idx_device_user (user_id),
    INDEX idx_device_blocked (is_blocked)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS odv_user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(128) NOT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    device_name VARCHAR(255) DEFAULT NULL,
    app_version VARCHAR(32) DEFAULT NULL,
    ip_address VARCHAR(64) DEFAULT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT NULL,
    expires_at DATETIME DEFAULT NULL,
    ended_at DATETIME DEFAULT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    UNIQUE KEY uniq_token_hash (token_hash),
    INDEX idx_session_user (user_id),
    INDEX idx_session_active (is_active, ended_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS odv_document_locks (
    upload_id VARCHAR(64) PRIMARY KEY,
    locked_by_user_id INT NOT NULL,
    locked_by_name VARCHAR(255) DEFAULT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    device_name VARCHAR(255) DEFAULT NULL,
    token_hash VARCHAR(128) DEFAULT NULL,
    locked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT NULL,
    expires_at DATETIME NOT NULL,
    INDEX idx_lock_expires (expires_at),
    INDEX idx_lock_user (locked_by_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
