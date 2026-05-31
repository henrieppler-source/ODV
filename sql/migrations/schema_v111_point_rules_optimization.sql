-- ODV v111 - optimierte Punkteregeln
-- Wird bevorzugt ueber Admin > Datenbank > Datenbankmigrationen pruefen/ausfuehren... ausgefuehrt.

CREATE TABLE IF NOT EXISTS point_rules_v110 LIKE point_rules;
INSERT IGNORE INTO point_rules_v110 SELECT * FROM point_rules;

ALTER TABLE point_rules
    ADD COLUMN IF NOT EXISTS rule_type VARCHAR(40) NOT NULL DEFAULT 'metadata' AFTER category,
    ADD COLUMN IF NOT EXISTS source_field VARCHAR(120) DEFAULT NULL AFTER rule_type,
    ADD COLUMN IF NOT EXISTS evaluation_source VARCHAR(30) DEFAULT NULL AFTER source_field,
    ADD COLUMN IF NOT EXISTS check_type VARCHAR(30) NOT NULL DEFAULT 'none' AFTER evaluation_source,
    ADD COLUMN IF NOT EXISTS min_value INT NOT NULL DEFAULT 0 AFTER check_type,
    ADD COLUMN IF NOT EXISTS is_system TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active;

-- Die eigentliche Aktualisierung erfolgt serverseitig versions- und jahresbezogen
-- ueber server/routes.php, damit das aktuelle Kalenderjahr verwendet wird.
