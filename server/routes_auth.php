<?php
declare(strict_types=1);

if ($method === 'GET' && $path === '/api/status') {
    $pdo = db();
    json_response([
        'success' => true,
        'message' => 'Ortschronik API läuft',
        'api_version' => ODV_API_VERSION,
        'version' => ODV_API_VERSION,
        'time' => date('c'),
        'maintenance' => maintenance_state($pdo),
        'app_update' => app_update_state($pdo)
    ]);
}

if ($method === 'GET' && $path === '/api/app-update') {
    $pdo = db();
    json_response(['success' => true, 'update' => app_update_state($pdo)]);
}

if ($method === 'PUT' && $path === '/api/admin/app-update') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $data = get_json_input();
    $version = trim((string)($data['version'] ?? ''));
    $fileName = trim((string)($data['file_name'] ?? $data['file'] ?? ''));
    $pathValue = trim((string)($data['nextcloud_relative_path'] ?? $data['path'] ?? ''));
    $sha256 = strtolower(trim((string)($data['sha256'] ?? '')));
    $required = !empty($data['required']) ? '1' : '0';
    $notes = trim((string)($data['release_notes'] ?? $data['notes'] ?? ''));
    if ($version === '') {
        json_response(['success' => false, 'error' => 'Version fehlt'], 422);
    }
    if ($fileName === '' && $pathValue === '') {
        json_response(['success' => false, 'error' => 'Dateiname oder Nextcloud-Relativpfad fehlt'], 422);
    }
    if ($sha256 !== '' && !preg_match('/^[a-f0-9]{64}$/', $sha256)) {
        json_response(['success' => false, 'error' => 'SHA256-Prüfsumme ist ungültig'], 422);
    }
    setting_set($pdo, 'app_update_version', $version);
    setting_set($pdo, 'app_update_file_name', $fileName);
    setting_set($pdo, 'app_update_nextcloud_relative_path', $pathValue);
    setting_set($pdo, 'app_update_sha256', $sha256);
    setting_set($pdo, 'app_update_required', $required);
    setting_set($pdo, 'app_update_release_notes', $notes);
    setting_set($pdo, 'app_update_published_at', date('Y-m-d H:i:s'));
    setting_set($pdo, 'app_update_published_by', (string)$currentUser['id']);
    json_response(['success' => true, 'update' => app_update_state($pdo)]);
}

// Nur noch angemeldete Superadmins dürfen den Datenbanktest ausführen.
if ($method === 'GET' && $path === '/api/db-test') {
    require_role(['superadmin']);
    $pdo = db();
    $stmt = $pdo->query('SELECT NOW() AS server_time');
    $row = $stmt->fetch();
    json_response([
        'success' => true,
        'message' => 'Datenbankverbindung erfolgreich',
        'server_time' => $row['server_time'] ?? null
    ]);
}

if ($method === 'POST' && $path === '/api/login') {
    $input = get_json_input();
    $username = trim((string)($input['username'] ?? ''));
    $password = (string)($input['password'] ?? '');

    if ($username === '' || $password === '') {
        json_response(['success' => false, 'error' => 'Benutzername und Passwort erforderlich'], 400);
    }

    $pdo = db();
    $stmt = $pdo->prepare("\n        SELECT id, username, password_hash, display_name, email, role, place, is_active\n        FROM users\n        WHERE username = :username\n        LIMIT 1\n    ");
    $stmt->execute([':username' => $username]);
    $user = $stmt->fetch();

    if (!$user || !password_verify($password, $user['password_hash'])) {
        record_login_attempt($pdo, $username, false);
        api_log('warning', 'Fehlgeschlagener Login', ['username' => $username]);
        json_response(['success' => false, 'error' => 'Benutzername oder Passwort falsch'], 401);
    }
    if ((int)$user['is_active'] !== 1) {
        json_response(['success' => false, 'error' => 'Benutzer ist deaktiviert'], 403);
    }
    $state = maintenance_state($pdo);
    if ($state['active'] && strtolower((string)$user['role']) !== 'superadmin') {
        json_response(['success' => false, 'error' => $state['message'], 'maintenance' => $state], 503);
    }

    $device = normalize_device_input($input);
    if (device_is_blocked($pdo, (int)$user['id'], $device['device_id'])) {
        json_response(['success' => false, 'error' => 'Dieses Gerät wurde für ODV gesperrt. Bitte wenden Sie sich an einen Superadmin.'], 403);
    }
    $isNewDevice = upsert_login_device($pdo, $user, $device);
    if ($isNewDevice) {
        notify_superadmins_new_device($pdo, $user, $device);
    }

    $plainToken = create_token();
    $hashedToken = token_hash($plainToken);
    $expiresAt = date('Y-m-d H:i:s', time() + 60 * 60 * 24 * 14);

    $insert = $pdo->prepare("\n        INSERT INTO api_tokens (user_id, token_hash, expires_at)\n        VALUES (:user_id, :token_hash, :expires_at)\n    ");
    $insert->execute([
        ':user_id' => $user['id'],
        ':token_hash' => $hashedToken,
        ':expires_at' => $expiresAt,
    ]);
    try {
        ensure_security_tables($pdo);
        $sessionInsert = $pdo->prepare("INSERT INTO odv_user_sessions (user_id, token_hash, device_id, device_name, app_version, ip_address, started_at, last_seen_at, expires_at, is_active) VALUES (:uid,:token_hash,:device_id,:device_name,:app_version,:ip,NOW(),NOW(),:expires_at,1)");
        $sessionInsert->execute([':uid'=>(int)$user['id'], ':token_hash'=>$hashedToken, ':device_id'=>$device['device_id'], ':device_name'=>$device['device_name'], ':app_version'=>$device['app_version'], ':ip'=>client_ip(), ':expires_at'=>$expiresAt]);
    } catch (Throwable $e) {
        api_log('warning', 'Login-Sitzung konnte nicht gespeichert werden', ['error'=>$e->getMessage()]);
    }

    record_login_attempt($pdo, $username, true);

    $updateLogin = $pdo->prepare("UPDATE users SET last_login_at = NOW() WHERE id = :id");
    $updateLogin->execute([':id' => $user['id']]);
    api_log('info', 'Login erfolgreich', ['user_id' => (int)$user['id'], 'username' => $user['username']]);

    json_response([
        'success' => true,
        'token' => $plainToken,
        'expires_at' => $expiresAt,
        'maintenance' => maintenance_state($pdo),
        'device' => ['is_new' => $isNewDevice, 'device_id' => $device['device_id'], 'device_name' => $device['device_name']],
        'sessions' => ['active_count' => active_session_count($pdo, (int)$user['id'])],
        'user' => [
            'id' => (int)$user['id'],
            'username' => $user['username'],
            'display_name' => $user['display_name'],
            'email' => $user['email'] ?? null,
            'role' => $user['role'],
            'place' => $user['place'],
        ]
    ]);
}

if ($method === 'GET' && $path === '/api/me') {
    $user = current_user();
    json_response([
        'success' => true,
        'user' => [
            'id' => $user['id'],
            'username' => $user['username'],
            'display_name' => $user['display_name'],
            'email' => $user['email'] ?? null,
            'role' => $user['role'],
            'place' => $user['place'],
        ]
    ]);
}

if ($method === 'POST' && $path === '/api/session/device') {
    $user = current_user();
    $input = get_json_input();
    $device = normalize_device_input($input);
    $pdo = db();
    ensure_security_tables($pdo);
    if (device_is_blocked($pdo, (int)$user['id'], $device['device_id'])) {
        json_response(['success' => false, 'error' => 'Dieses Gerät wurde für ODV gesperrt. Bitte wenden Sie sich an einen Superadmin.'], 403);
    }
    try {
        // Gerätedatensatz bei jedem Start/API-Heartbeat aktualisieren, damit die angezeigte ODV-Version nach Updates stimmt.
        // last_login_at bleibt der echte Login-Zeitpunkt; hier wird nur last_seen_at/App-Version aktualisiert.
        $existingDevice = $pdo->prepare("SELECT id FROM odv_user_devices WHERE user_id=:uid AND device_id=:did LIMIT 1");
        $existingDevice->execute([':uid'=>(int)$user['id'], ':did'=>$device['device_id']]);
        $deviceRow = $existingDevice->fetch();
        if ($deviceRow) {
            $updDev = $pdo->prepare("UPDATE odv_user_devices SET device_name=:device_name, windows_user=:windows_user, os_name=:os_name, os_version=:os_version, app_version=:app_version, last_seen_at=NOW(), last_ip=:ip WHERE id=:id");
            $updDev->execute([':device_name'=>$device['device_name'], ':windows_user'=>$device['windows_user'], ':os_name'=>$device['os_name'], ':os_version'=>$device['os_version'], ':app_version'=>$device['app_version'], ':ip'=>client_ip(), ':id'=>$deviceRow['id']]);
        } else {
            $insDev = $pdo->prepare("INSERT INTO odv_user_devices (user_id, device_id, device_name, windows_user, os_name, os_version, app_version, first_seen_at, last_seen_at, last_login_at, last_ip) VALUES (:uid,:did,:device_name,:windows_user,:os_name,:os_version,:app_version,NOW(),NOW(),NOW(),:ip)");
            $insDev->execute([':uid'=>(int)$user['id'], ':did'=>$device['device_id'], ':device_name'=>$device['device_name'], ':windows_user'=>$device['windows_user'], ':os_name'=>$device['os_name'], ':os_version'=>$device['os_version'], ':app_version'=>$device['app_version'], ':ip'=>client_ip()]);
        }
        $tokenHash = get_token_hash_for_request();
        if ($tokenHash !== '') {
            $stmt = $pdo->prepare("UPDATE odv_user_sessions SET device_id=:device_id, device_name=:device_name, app_version=:app_version, ip_address=:ip, last_seen_at=NOW() WHERE token_hash=:token_hash AND ended_at IS NULL");
            $stmt->execute([
                ':device_id' => $device['device_id'],
                ':device_name' => $device['device_name'],
                ':app_version' => $device['app_version'],
                ':ip' => client_ip(),
                ':token_hash' => $tokenHash,
            ]);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Sitzungs-/Geräteversion konnte nicht aktualisiert werden', ['error' => $e->getMessage()]);
        json_response(['success'=>false, 'error'=>'Sitzungs-/Geräteversion konnte nicht aktualisiert werden'], 500);
    }
    json_response(['success'=>true, 'device'=>['device_id'=>$device['device_id'], 'app_version'=>$device['app_version']]]);
}

if ($method === 'POST' && $path === '/api/logout') {
    $token = get_authorization_token();
    if ($token) {
        $pdo = db();
        $hash = token_hash($token);
        try {
            ensure_security_tables($pdo);
            $pdo->prepare("UPDATE odv_user_sessions SET is_active=0, ended_at=NOW() WHERE token_hash=:token_hash")->execute([':token_hash'=>$hash]);
        } catch (Throwable $e) {}
        $stmt = $pdo->prepare("DELETE FROM api_tokens WHERE token_hash = :token_hash");
        $stmt->execute([':token_hash' => $hash]);
    }
    json_response(['success' => true, 'message' => 'Abgemeldet']);
}
