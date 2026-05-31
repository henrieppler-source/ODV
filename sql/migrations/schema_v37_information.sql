-- v37: Standardrechte für neuen Bereich 03_INFORMATION
-- Die Tabelle user_folder_permissions muss bereits aus v27 vorhanden sein.
-- Admin/Superadmin: lesen und schreiben; Ortschronisten: lesen ja, schreiben nein.

INSERT INTO user_folder_permissions (user_id, folder_group, can_read, can_write, updated_by_user_id)
SELECT id, '03_INFORMATION', 1, CASE WHEN LOWER(role) IN ('admin', 'superadmin') THEN 1 ELSE 0 END, NULL
FROM users
ON DUPLICATE KEY UPDATE
    can_read = VALUES(can_read),
    can_write = VALUES(can_write),
    updated_at = CURRENT_TIMESTAMP;
