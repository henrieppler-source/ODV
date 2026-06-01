<?php
declare(strict_types=1);

if ($method === 'GET' && $path === '/api/admin/sessions') {
    require_role(['superadmin']);
    $pdo = db();
    ensure_security_tables($pdo);
    $pdo->exec("UPDATE odv_user_sessions SET is_active=0, ended_at=NOW() WHERE ended_at IS NULL AND expires_at < NOW()");
    $sessions = $pdo->query("SELECT s.id AS session_id, s.user_id, u.display_name, u.username, s.device_id, s.device_name, s.app_version, s.ip_address, s.started_at, s.last_seen_at, s.expires_at, s.is_active FROM odv_user_sessions s INNER JOIN users u ON u.id=s.user_id WHERE s.is_active=1 AND s.ended_at IS NULL ORDER BY s.last_seen_at DESC, s.started_at DESC")->fetchAll();
    $devices = $pdo->query("SELECT d.*, u.display_name, u.username FROM odv_user_devices d INNER JOIN users u ON u.id=d.user_id ORDER BY d.last_login_at DESC, d.updated_at DESC")->fetchAll();
    json_response(['success'=>true, 'sessions'=>$sessions, 'devices'=>$devices]);
}

if ($method === 'POST' && $path === '/api/admin/sessions/end') {
    require_role(['superadmin']);
    $input = get_json_input();
    $sessionId = (int)($input['session_id'] ?? 0);
    if ($sessionId <= 0) { json_response(['success'=>false, 'error'=>'Sitzungs-ID fehlt'], 400); }
    $pdo = db();
    ensure_security_tables($pdo);
    $stmt = $pdo->prepare("SELECT token_hash FROM odv_user_sessions WHERE id=:id LIMIT 1");
    $stmt->execute([':id'=>$sessionId]);
    $row = $stmt->fetch();
    if ($row) {
        $pdo->prepare("UPDATE odv_user_sessions SET is_active=0, ended_at=NOW() WHERE id=:id")->execute([':id'=>$sessionId]);
        $pdo->prepare("DELETE FROM api_tokens WHERE token_hash=:token_hash")->execute([':token_hash'=>$row['token_hash']]);
    }
    json_response(['success'=>true, 'message'=>'Sitzung beendet']);
}

if ($method === 'POST' && $path === '/api/admin/devices/block') {
    require_role(['superadmin']);
    $input = get_json_input();
    $userId = (int)($input['user_id'] ?? 0);
    $deviceId = trim((string)($input['device_id'] ?? ''));
    $blocked = !empty($input['blocked']) ? 1 : 0;
    if ($userId <= 0 || $deviceId === '') { json_response(['success'=>false, 'error'=>'Benutzer oder Gerät fehlt'], 400); }
    $pdo = db();
    ensure_security_tables($pdo);
    $stmt = $pdo->prepare("UPDATE odv_user_devices SET is_blocked=:blocked WHERE user_id=:uid AND device_id=:did");
    $stmt->execute([':blocked'=>$blocked, ':uid'=>$userId, ':did'=>$deviceId]);
    if ($blocked) {
        $pdo->prepare("UPDATE odv_user_sessions SET is_active=0, ended_at=NOW() WHERE user_id=:uid AND device_id=:did AND ended_at IS NULL")->execute([':uid'=>$userId, ':did'=>$deviceId]);
        $pdo->prepare("DELETE t FROM api_tokens t INNER JOIN odv_user_sessions s ON s.token_hash=t.token_hash WHERE s.user_id=:uid AND s.device_id=:did")->execute([':uid'=>$userId, ':did'=>$deviceId]);
    }
    json_response(['success'=>true, 'message'=>$blocked ? 'Gerät gesperrt' : 'Gerät freigegeben']);
}

if ($method === 'GET' && $path === '/api/users') {
    require_role(['superadmin']);
    $pdo = db();
    ensure_user_nextcloud_columns($pdo);
    $stmt = $pdo->query("\n        SELECT id, username, display_name, email, nextcloud_username,\n               CASE WHEN COALESCE(nextcloud_password_enc, '') <> '' THEN 1 ELSE 0 END AS nextcloud_password_saved,\n               role, place, is_active, last_login_at, created_at, updated_at\n        FROM users\n        ORDER BY display_name ASC, username ASC\n    ");
    json_response(['success' => true, 'users' => $stmt->fetchAll()]);
}

if ($method === 'POST' && $path === '/api/users') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $username = trim((string)($input['username'] ?? ''));
    $password = (string)($input['password'] ?? '');
    $displayName = trim((string)($input['display_name'] ?? ''));
    $email = trim((string)($input['email'] ?? ''));
    $nextcloudUsername = trim((string)($input['nextcloud_username'] ?? ''));
    $nextcloudPassword = (string)($input['nextcloud_password'] ?? '');
    $role = normalize_role((string)($input['role'] ?? 'ortschronist'));
    $place = trim((string)($input['place'] ?? ''));
    $isActive = isset($input['is_active']) ? (int)(bool)$input['is_active'] : 1;

    if ($username === '' || $password === '' || $displayName === '') {
        json_response(['success' => false, 'error' => 'Benutzername, Passwort und Name sind erforderlich'], 400);
    }

    $passwordHash = password_hash($password, PASSWORD_DEFAULT);
    $pdo = db();
    ensure_user_nextcloud_columns($pdo);

    try {
        $nextcloudPasswordEnc = $nextcloudPassword !== '' ? encrypt_nextcloud_credential($pdo, $nextcloudPassword) : '';
        $stmt = $pdo->prepare("\n            INSERT INTO users (username, password_hash, display_name, email, nextcloud_username, nextcloud_password_enc, role, place, is_active)\n            VALUES (:username, :password_hash, :display_name, :email, :nextcloud_username, :nextcloud_password_enc, :role, :place, :is_active)\n        ");
        $stmt->execute([
            ':username' => $username,
            ':password_hash' => $passwordHash,
            ':display_name' => $displayName,
            ':email' => $email !== '' ? $email : null,
            ':nextcloud_username' => $nextcloudUsername !== '' ? $nextcloudUsername : null,
            ':nextcloud_password_enc' => $nextcloudPasswordEnc !== '' ? $nextcloudPasswordEnc : null,
            ':role' => $role,
            ':place' => $place !== '' ? $place : null,
            ':is_active' => $isActive,
        ]);
        $newUserId = (int)$pdo->lastInsertId();
        api_log('info', 'Benutzer angelegt', ['by_user_id' => $currentUser['id'], 'new_user_id' => $newUserId]);
        json_response(['success' => true, 'message' => 'Benutzer wurde angelegt', 'user_id' => $newUserId], 201);
    } catch (PDOException $e) {
        if ((int)$e->getCode() === 23000) {
            json_response(['success' => false, 'error' => 'Benutzername ist bereits vorhanden'], 409);
        }
        api_log('error', 'Benutzer konnte nicht angelegt werden', ['pdo_code' => $e->getCode()]);
        json_response(['success' => false, 'error' => 'Benutzer konnte nicht angelegt werden'], 500);
    }
}

if ($method === 'PUT' && preg_match('#^/api/users/(\d+)$#', $path, $matches)) {
    $currentUser = require_role(['superadmin']);
    $userId = (int)$matches[1];
    $input = get_json_input();

    $username = trim((string)($input['username'] ?? ''));
    $password = (string)($input['password'] ?? '');
    $displayName = trim((string)($input['display_name'] ?? ''));
    $email = trim((string)($input['email'] ?? ''));
    $role = normalize_role((string)($input['role'] ?? 'ortschronist'));
    $place = trim((string)($input['place'] ?? ''));
    $isActive = isset($input['is_active']) ? (int)(bool)$input['is_active'] : 1;

    if ($username === '' || $displayName === '') {
        json_response(['success' => false, 'error' => 'Benutzername und Name sind erforderlich'], 400);
    }

    // Serverseitiger Selbstschutz: Ein angemeldeter Benutzer darf sich nicht selbst deaktivieren oder die eigene Rolle ändern.
    if ($userId === (int)$currentUser['id']) {
        if ($isActive !== 1) {
            json_response(['success' => false, 'error' => 'Der aktuell angemeldete Benutzer darf sich nicht selbst deaktivieren'], 400);
        }
        if ($role !== $currentUser['role']) {
            json_response(['success' => false, 'error' => 'Der aktuell angemeldete Benutzer darf die eigene Rolle nicht ändern'], 400);
        }
    }

    $pdo = db();
    ensure_user_nextcloud_columns($pdo);
    try {
        if ($password !== '') {
            $passwordHash = password_hash($password, PASSWORD_DEFAULT);
            $stmt = $pdo->prepare("\n                UPDATE users\n                SET username = :username, password_hash = :password_hash, display_name = :display_name, email = :email, nextcloud_username = :nextcloud_username, role = :role, place = :place, is_active = :is_active\n                WHERE id = :id\n            ");
            $stmt->execute([
                ':id' => $userId,
                ':username' => $username,
                ':password_hash' => $passwordHash,
                ':display_name' => $displayName,
                ':email' => $email !== '' ? $email : null,
                ':nextcloud_username' => $nextcloudUsername !== '' ? $nextcloudUsername : null,
                ':role' => $role,
                ':place' => $place !== '' ? $place : null,
                ':is_active' => $isActive,
            ]);
        } else {
            $stmt = $pdo->prepare("\n                UPDATE users\n                SET username = :username, display_name = :display_name, email = :email, nextcloud_username = :nextcloud_username, role = :role, place = :place, is_active = :is_active\n                WHERE id = :id\n            ");
            $stmt->execute([
                ':id' => $userId,
                ':username' => $username,
                ':display_name' => $displayName,
                ':email' => $email !== '' ? $email : null,
                ':nextcloud_username' => $nextcloudUsername !== '' ? $nextcloudUsername : null,
                ':role' => $role,
                ':place' => $place !== '' ? $place : null,
                ':is_active' => $isActive,
            ]);
        }
        if ($nextcloudPassword !== '') {
            $enc = encrypt_nextcloud_credential($pdo, $nextcloudPassword);
            $pdo->prepare("UPDATE users SET nextcloud_password_enc = :enc WHERE id = :id")->execute([':enc' => $enc, ':id' => $userId]);
        }
        api_log('info', 'Benutzer gespeichert', ['by_user_id' => $currentUser['id'], 'user_id' => $userId]);
        json_response(['success' => true, 'message' => 'Benutzer wurde gespeichert', 'user_id' => $userId]);
    } catch (PDOException $e) {
        if ((int)$e->getCode() === 23000) {
            json_response(['success' => false, 'error' => 'Benutzername ist bereits vorhanden'], 409);
        }
        api_log('error', 'Benutzer konnte nicht gespeichert werden', ['pdo_code' => $e->getCode()]);
        json_response(['success' => false, 'error' => 'Benutzer konnte nicht gespeichert werden'], 500);
    }
}
