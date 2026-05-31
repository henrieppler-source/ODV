# v33 API-500-Fix

Diese Version behebt einen serverseitigen 500-Fehler beim Laden der Dokumentliste.

## Ursache

In `current_user()` wurde versehentlich `login_limit_check($pdo, $username)` ausgeführt. Die Variable `$username` existiert dort nicht. Da `strict_types=1` aktiv ist, kann daraus ein fataler Fehler werden.

## Änderung

- Login-Limit-Prüfung bleibt nur im Login-Kontext.
- `current_user()` prüft nur noch das Bearer-Token.
- Rollenprüfung ist robuster gegen Groß-/Kleinschreibung.

## Serverdatei

`server/routes_v33.php` als `ortschronik-api/routes.php` hochladen.
