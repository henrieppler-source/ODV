-- ODV v69: Updateverwaltung über Nextcloud

CREATE TABLE IF NOT EXISTS system_settings (
  setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
  setting_value TEXT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Genutzte Keys in system_settings:
-- app_update_version
-- app_update_file_name
-- app_update_nextcloud_relative_path
-- app_update_sha256
-- app_update_required
-- app_update_release_notes
-- app_update_published_at
-- app_update_published_by
