-- Testdatensätze entfernen.
-- Vor Ausführung prüfen, ob die upload_id wirklich nur Testdaten betrifft.

DELETE FROM document_persons
WHERE document_id IN (
    SELECT id FROM documents WHERE upload_id LIKE 'test-%'
);

DELETE FROM document_history
WHERE upload_id LIKE 'test-%';

DELETE FROM documents
WHERE upload_id LIKE 'test-%';

-- Optionale Testbenutzer entfernen/deaktivieren.
-- Besser erst deaktivieren statt löschen, falls schon Historieneinträge vorhanden sind.
UPDATE users
SET is_active = 0
WHERE username IN ('oc_milz_01', 'test_admin', 'test_superadmin');
