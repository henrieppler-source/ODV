-- ODV v49: Punkte nur für Dateien, die in 01_ABLAGE_ORTSCHRONIK oder 06_UNSERE_ARBEITEN / 06_ARBEIT_DER_ORTSCHRONISTEN hochgeladen wurden.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS points_eligible TINYINT(1) NOT NULL DEFAULT 0 AFTER current_path;

UPDATE documents
SET points_eligible = CASE
  WHEN LOWER(REPLACE(COALESCE(target_folder, ''), '\\', '/')) LIKE '%/01_ablage_ortschronik/%'
    OR LOWER(REPLACE(COALESCE(target_folder, ''), '\\', '/')) LIKE '%/06_unsere_arbeiten/%'
    OR LOWER(REPLACE(COALESCE(target_folder, ''), '\\', '/')) LIKE '%/06_arbeit_der_ortschronisten/%'
    OR LOWER(REPLACE(COALESCE(target_folder, ''), '\\', '/')) LIKE '%/06_arbeiten_der_ortschronisten/%'
    OR LOWER(REPLACE(COALESCE(current_path, ''), '\\', '/')) LIKE '%/01_ablage_ortschronik/%'
    OR LOWER(REPLACE(COALESCE(current_path, ''), '\\', '/')) LIKE '%/06_unsere_arbeiten/%'
    OR LOWER(REPLACE(COALESCE(current_path, ''), '\\', '/')) LIKE '%/06_arbeit_der_ortschronisten/%'
    OR LOWER(REPLACE(COALESCE(current_path, ''), '\\', '/')) LIKE '%/06_arbeiten_der_ortschronisten/%'
  THEN 1 ELSE 0 END
WHERE points_eligible = 0;

-- Bereits versehentlich erzeugte automatische Punkte für nicht berechtigte Dokumente ausblenden.
-- Manuelle Sonderpunkte bleiben dokumentiert, werden aber in der Jahresauswertung durch die Dokumentregel ebenfalls nicht berücksichtigt, wenn das Dokument nicht punkteberechtigt ist.
UPDATE contribution_points cp
JOIN documents d ON d.id = cp.document_id
SET cp.is_confirmed = 0
WHERE COALESCE(d.points_eligible, 0) = 0
  AND cp.is_confirmed = 1;
