-- ODV v106 - serverseitiges Migrationsprotokoll
-- Wird bevorzugt ueber Admin > Datenbankmigrationen pruefen/ausfuehren... ausgefuehrt.

CREATE TABLE IF NOT EXISTS odv_schema_migrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    migration_key VARCHAR(100) NOT NULL,
    from_version VARCHAR(20) NOT NULL,
    to_version VARCHAR(20) NOT NULL,
    description TEXT DEFAULT NULL,
    backup_tables TEXT DEFAULT NULL,
    executed_by_user_id INT DEFAULT NULL,
    executed_by_name VARCHAR(255) DEFAULT NULL,
    executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_migration_key (migration_key),
    INDEX idx_schema_migrations_executed_at (executed_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
