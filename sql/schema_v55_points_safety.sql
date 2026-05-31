-- ODV v55: Sicherheitsmigration für Punkte-Nachberechnung.
-- Vor dem Import bitte Datenbank sichern.
-- Ergänzt fehlende Spalten aus v48/v49 defensiv und berechnet points_eligible robuster.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS keywords TEXT DEFAULT NULL AFTER note,
    ADD COLUMN IF NOT EXISTS transcription_done TINYINT(1) NOT NULL DEFAULT 0 AFTER keywords,
    ADD COLUMN IF NOT EXISTS transcription_type VARCHAR(100) DEFAULT NULL AFTER transcription_done,
    ADD COLUMN IF NOT EXISTS transcription_note TEXT DEFAULT NULL AFTER transcription_type,
    ADD COLUMN IF NOT EXISTS points_eligible TINYINT(1) NOT NULL DEFAULT 0 AFTER current_path;

ALTER TABLE contribution_points
    ADD COLUMN IF NOT EXISTS source_field VARCHAR(120) DEFAULT NULL AFTER reason,
    ADD COLUMN IF NOT EXISTS is_manual TINYINT(1) NOT NULL DEFAULT 0 AFTER created_by_name,
    ADD COLUMN IF NOT EXISTS is_confirmed TINYINT(1) NOT NULL DEFAULT 1 AFTER is_manual;

ALTER TABLE document_persons
    ADD COLUMN IF NOT EXISTS created_by_user_id INT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS created_by_name VARCHAR(200) DEFAULT NULL;

UPDATE documents
SET points_eligible = CASE
  WHEN LOWER(REPLACE(CONCAT('/', COALESCE(target_folder, ''), '/'), '\\', '/')) LIKE '%/01_ablage_ortschronik/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(target_folder, ''), '/'), '\\', '/')) LIKE '%/06_unsere_arbeiten/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(target_folder, ''), '/'), '\\', '/')) LIKE '%/06_arbeit_der_ortschronisten/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(target_folder, ''), '/'), '\\', '/')) LIKE '%/06_arbeiten_der_ortschronisten/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(current_path, ''), '/'), '\\', '/')) LIKE '%/01_ablage_ortschronik/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(current_path, ''), '/'), '\\', '/')) LIKE '%/06_unsere_arbeiten/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(current_path, ''), '/'), '\\', '/')) LIKE '%/06_arbeit_der_ortschronisten/%'
    OR LOWER(REPLACE(CONCAT('/', COALESCE(current_path, ''), '/'), '\\', '/')) LIKE '%/06_arbeiten_der_ortschronisten/%'
  THEN 1 ELSE 0 END;
