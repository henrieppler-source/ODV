-- v29 Produktiv-Härtung: Login-Versuche für Rate-Limiting protokollieren
CREATE TABLE IF NOT EXISTS api_login_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    success TINYINT(1) NOT NULL DEFAULT 0,
    attempted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_login_attempts_user_time (username, attempted_at),
    INDEX idx_login_attempts_ip_time (ip_address, attempted_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
