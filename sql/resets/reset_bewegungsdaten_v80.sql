-- ODV v74: Reset der Dokument- und Punkte-Testdaten
-- Löscht KEINE Stammdaten/Verwaltungsdaten:
--   users, user_folder_permissions, place_folders, point_rules,
--   mail_groups, mail_group_members, settings usw. bleiben erhalten.
-- Löscht KEINE Dateien in Nextcloud.
--
-- Leert nur vorhandene Tabellen. Nicht vorhandene Tabellen werden übersprungen.

DELIMITER $$

DROP PROCEDURE IF EXISTS odv_reset_bewegungsdaten_v74 $$
CREATE PROCEDURE odv_reset_bewegungsdaten_v74()
BEGIN
  DECLARE tbl_exists INT DEFAULT 0;

  SET FOREIGN_KEY_CHECKS = 0;

  -- Punkte / Beitragsereignisse zuerst
  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'contribution_points';
  IF tbl_exists > 0 THEN DELETE FROM contribution_points; ALTER TABLE contribution_points AUTO_INCREMENT = 1; END IF;
  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'manual_special_points';
  IF tbl_exists > 0 THEN DELETE FROM manual_special_points; ALTER TABLE manual_special_points AUTO_INCREMENT = 1; END IF;

  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'point_events';
  IF tbl_exists > 0 THEN DELETE FROM point_events; ALTER TABLE point_events AUTO_INCREMENT = 1; END IF;

  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'point_adjustments';
  IF tbl_exists > 0 THEN DELETE FROM point_adjustments; ALTER TABLE point_adjustments AUTO_INCREMENT = 1; END IF;

  -- Dokumentbezogene Nebentabellen
  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'document_persons';
  IF tbl_exists > 0 THEN DELETE FROM document_persons; ALTER TABLE document_persons AUTO_INCREMENT = 1; END IF;

  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'document_history';
  IF tbl_exists > 0 THEN DELETE FROM document_history; ALTER TABLE document_history AUTO_INCREMENT = 1; END IF;

  -- Haupttabelle zuletzt
  SELECT COUNT(*) INTO tbl_exists FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'documents';
  IF tbl_exists > 0 THEN DELETE FROM documents; ALTER TABLE documents AUTO_INCREMENT = 1; END IF;

  SET FOREIGN_KEY_CHECKS = 1;
END $$

DELIMITER ;

CALL odv_reset_bewegungsdaten_v74();
DROP PROCEDURE IF EXISTS odv_reset_bewegungsdaten_v74;
