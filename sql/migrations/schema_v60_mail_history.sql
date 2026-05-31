-- ODV v60: Mail-Versandhistorie
-- Vor dem Import bitte Datenbank sichern.

CREATE TABLE IF NOT EXISTS mail_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_by_user_id INT DEFAULT NULL,
    sent_by_name VARCHAR(255) DEFAULT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body_preview TEXT DEFAULT NULL,
    mode VARCHAR(50) DEFAULT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'sent',
    error_message TEXT DEFAULT NULL,
    documents_json LONGTEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mail_history_sent_at (sent_at),
    INDEX idx_mail_history_recipient (recipient_email),
    INDEX idx_mail_history_sender (sent_by_user_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
