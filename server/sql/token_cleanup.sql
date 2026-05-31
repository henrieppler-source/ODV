-- Abgelaufene API-Tokens entfernen
DELETE FROM api_tokens
WHERE expires_at < NOW();
