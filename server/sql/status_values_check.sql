-- Überblick über verwendete Statuswerte
SELECT status, COUNT(*) AS anzahl
FROM documents
GROUP BY status
ORDER BY status;

-- Empfohlene Statuswerte im Testbetrieb:
-- hochgeladen
-- erfasst
-- geaendert
-- rueckfrage
-- geprueft
-- archiviert
