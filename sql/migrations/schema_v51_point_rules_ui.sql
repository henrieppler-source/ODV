-- ODV v51: zusätzliche Standardregeln für Sonderpunkte und Bedienfelder
-- Kann mehrfach ausgeführt werden. Legt nur fehlende/aktualisierte Punkteregeln für das aktuelle Kalenderjahr an.

INSERT INTO point_rules (year, rule_key, label, category, points, is_active)
VALUES
(YEAR(CURDATE()), 'manual_transcription_old_handwriting', 'Transkription alte Handschrift', 'manual_bonus', 5, 1),
(YEAR(CURDATE()), 'manual_chronicle_article', 'Ausgearbeiteter Chronikartikel', 'manual_bonus', 5, 1),
(YEAR(CURDATE()), 'manual_research_sources', 'Recherche mit Quellenapparat', 'manual_bonus', 8, 1),
(YEAR(CURDATE()), 'manual_photo_collection', 'Erschließung eines Fotobestands', 'manual_bonus', 10, 1),
(YEAR(CURDATE()), 'manual_special_work', 'Besondere Zuarbeit', 'manual_bonus', 0, 1)
ON DUPLICATE KEY UPDATE
    label = VALUES(label),
    category = VALUES(category),
    points = VALUES(points),
    is_active = VALUES(is_active);
