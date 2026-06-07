<?php

declare(strict_types=1);

function login_limit_check(PDO $pdo, string $username): void

{

    // Fallback: Wenn Migration noch nicht eingespielt ist, blockiert die API nicht.

    try {

        $ip = client_ip();

        $stmt = $pdo->prepare("
            SELECT COUNT(*) AS cnt
            FROM api_login_attempts
            WHERE success = 0
              AND attempted_at >= (NOW() - INTERVAL 15 MINUTE)
              AND (username = :username OR ip_address = :ip)
        ");

        $stmt->execute([':username' => $username, ':ip' => $ip]);

        $row = $stmt->fetch();

        if ((int)($row['cnt'] ?? 0) >= 10) {

            api_log('warning', 'Login vorübergehend gesperrt', ['username' => $username, 'ip' => $ip]);

            json_response(['success' => false, 'error' => 'Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen.'], 429);

        }

    } catch (Throwable $e) {

        api_log('warning', 'Login-Limit konnte nicht geprüft werden', ['error' => $e->getMessage()]);

    }

}

function record_login_attempt(PDO $pdo, string $username, bool $success): void

{

    try {

        $stmt = $pdo->prepare("
            INSERT INTO api_login_attempts (username, ip_address, success)
            VALUES (:username, :ip_address, :success)
        ");

        $stmt->execute([

            ':username' => $username,

            ':ip_address' => client_ip(),

            ':success' => $success ? 1 : 0,

        ]);

    } catch (Throwable $e) {

        // Nicht kritisch; Login selbst soll daran nicht scheitern.

    }

}

function ensure_security_tables(PDO $pdo): void

{

    $pdo->exec("CREATE TABLE IF NOT EXISTS odv_user_devices (

        id INT AUTO_INCREMENT PRIMARY KEY,

        user_id INT NOT NULL,

        device_id VARCHAR(128) NOT NULL,

        device_name VARCHAR(255) DEFAULT NULL,

        windows_user VARCHAR(255) DEFAULT NULL,

        os_name VARCHAR(128) DEFAULT NULL,

        os_version VARCHAR(255) DEFAULT NULL,

        app_version VARCHAR(32) DEFAULT NULL,

        first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        last_seen_at DATETIME DEFAULT NULL,

        last_login_at DATETIME DEFAULT NULL,

        last_ip VARCHAR(64) DEFAULT NULL,

        is_blocked TINYINT(1) NOT NULL DEFAULT 0,

        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

        UNIQUE KEY uniq_user_device (user_id, device_id),

        INDEX idx_device_user (user_id),

        INDEX idx_device_blocked (is_blocked)

    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS odv_user_sessions (

        id INT AUTO_INCREMENT PRIMARY KEY,

        user_id INT NOT NULL,

        token_hash VARCHAR(128) NOT NULL,

        device_id VARCHAR(128) DEFAULT NULL,

        device_name VARCHAR(255) DEFAULT NULL,

        app_version VARCHAR(32) DEFAULT NULL,

        ip_address VARCHAR(64) DEFAULT NULL,

        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        last_seen_at DATETIME DEFAULT NULL,

        expires_at DATETIME DEFAULT NULL,

        ended_at DATETIME DEFAULT NULL,

        is_active TINYINT(1) NOT NULL DEFAULT 1,

        UNIQUE KEY uniq_token_hash (token_hash),

        INDEX idx_session_user (user_id),

        INDEX idx_session_active (is_active, ended_at)

    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS odv_document_locks (

        upload_id VARCHAR(64) PRIMARY KEY,

        locked_by_user_id INT NOT NULL,

        locked_by_name VARCHAR(255) DEFAULT NULL,

        device_id VARCHAR(128) DEFAULT NULL,

        device_name VARCHAR(255) DEFAULT NULL,

        token_hash VARCHAR(128) DEFAULT NULL,

        locked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        last_seen_at DATETIME DEFAULT NULL,

        expires_at DATETIME NOT NULL,

        INDEX idx_lock_expires (expires_at),

        INDEX idx_lock_user (locked_by_user_id)

    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

}

function normalize_device_input(array $input): array

{

    $device = is_array($input['device'] ?? null) ? $input['device'] : [];

    $deviceId = trim((string)($device['device_id'] ?? ''));

    if ($deviceId === '') { $deviceId = 'unknown-' . substr(hash('sha256', client_ip() . ($_SERVER['HTTP_USER_AGENT'] ?? '')), 0, 32); }

    return [

        'device_id' => substr($deviceId, 0, 128),

        'device_name' => substr(trim((string)($device['device_name'] ?? 'Unbekanntes Gerät')), 0, 255),

        'windows_user' => substr(trim((string)($device['windows_user'] ?? '')), 0, 255),

        'os_name' => substr(trim((string)($device['os_name'] ?? '')), 0, 128),

        'os_version' => substr(trim((string)($device['os_version'] ?? '')), 0, 255),

        'app_version' => substr(trim((string)($device['app_version'] ?? '')), 0, 32),

    ];

}

function device_is_blocked(PDO $pdo, int $userId, string $deviceId): bool

{

    ensure_security_tables($pdo);

    $stmt = $pdo->prepare("SELECT is_blocked FROM odv_user_devices WHERE user_id=:uid AND device_id=:did LIMIT 1");

    $stmt->execute([':uid'=>$userId, ':did'=>$deviceId]);

    $row = $stmt->fetch();

    return $row && (int)$row['is_blocked'] === 1;

}

function upsert_login_device(PDO $pdo, array $user, array $device): bool

{

    ensure_security_tables($pdo);

    $stmt = $pdo->prepare("SELECT id FROM odv_user_devices WHERE user_id=:uid AND device_id=:did LIMIT 1");

    $stmt->execute([':uid'=>(int)$user['id'], ':did'=>$device['device_id']]);

    $existing = $stmt->fetch();

    if ($existing) {

        $upd = $pdo->prepare("UPDATE odv_user_devices SET device_name=:device_name, windows_user=:windows_user, os_name=:os_name, os_version=:os_version, app_version=:app_version, last_seen_at=NOW(), last_login_at=NOW(), last_ip=:ip WHERE id=:id");

        $upd->execute([':device_name'=>$device['device_name'], ':windows_user'=>$device['windows_user'], ':os_name'=>$device['os_name'], ':os_version'=>$device['os_version'], ':app_version'=>$device['app_version'], ':ip'=>client_ip(), ':id'=>$existing['id']]);

        return false;

    }

    $ins = $pdo->prepare("INSERT INTO odv_user_devices (user_id, device_id, device_name, windows_user, os_name, os_version, app_version, first_seen_at, last_seen_at, last_login_at, last_ip) VALUES (:uid,:did,:device_name,:windows_user,:os_name,:os_version,:app_version,NOW(),NOW(),NOW(),:ip)");

    $ins->execute([':uid'=>(int)$user['id'], ':did'=>$device['device_id'], ':device_name'=>$device['device_name'], ':windows_user'=>$device['windows_user'], ':os_name'=>$device['os_name'], ':os_version'=>$device['os_version'], ':app_version'=>$device['app_version'], ':ip'=>client_ip()]);

    return true;

}

function active_session_count(PDO $pdo, int $userId): int

{

    ensure_security_tables($pdo);

    $pdo->prepare("UPDATE odv_user_sessions SET is_active=0, ended_at=NOW() WHERE user_id=:uid AND ended_at IS NULL AND expires_at < NOW()")->execute([':uid'=>$userId]);

    $stmt = $pdo->prepare("SELECT COUNT(*) AS cnt FROM odv_user_sessions WHERE user_id=:uid AND is_active=1 AND ended_at IS NULL AND (expires_at IS NULL OR expires_at >= NOW())");

    $stmt->execute([':uid'=>$userId]);

    $row = $stmt->fetch();

    return (int)($row['cnt'] ?? 0);

}

function notify_superadmins_new_device(PDO $pdo, array $user, array $device): void

{

    try {

        $stmt = $pdo->query("SELECT email FROM users WHERE is_active=1 AND LOWER(role)='superadmin' AND email IS NOT NULL AND email <> ''");

        $emails = [];

        foreach ($stmt->fetchAll() as $row) {

            $email = is_array($row) ? trim((string)($row['email'] ?? '')) : '';

            if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {

                continue;

            }

            $emails[strtolower($email)] = $email;

        }

        if (!$emails) {

            return;

        }

        $subject = 'ODV: Neue Anmeldung von unbekanntem Gerät';

        $body = "Neue ODV-Anmeldung von unbekanntem Gerät\n\n" .

            "Benutzer: " . ($user['display_name'] ?? $user['username'] ?? '') . "\n" .

            "Benutzername: " . ($user['username'] ?? '') . "\n" .

            "Rolle: " . ($user['role'] ?? '') . "\n" .

            "Gerät: " . ($device['device_name'] ?? '') . "\n" .

            "Windows-Benutzer: " . ($device['windows_user'] ?? '') . "\n" .

            "ODV-Version: " . ($device['app_version'] ?? '') . "\n" .

            "IP-Adresse: " . client_ip() . "\n" .

            "Zeitpunkt: " . date('Y-m-d H:i:s') . "\n\n" .

            "Das Gerät wurde automatisch zugelassen. Bei Bedarf kann der Superadmin es in ODV sperren.";

        foreach ($emails as $email) { @send_text_mail($email, $subject, $body); }

    } catch (Throwable $e) {

        api_log('warning', 'Superadmin-Info zu neuem Gerät konnte nicht versendet werden', ['error'=>$e->getMessage()]);

    }

}

function get_token_hash_for_request(): string

{

    $token = get_authorization_token();

    return $token ? token_hash($token) : '';

}

function current_session_device(PDO $pdo): array

{

    ensure_security_tables($pdo);

    $hash = get_token_hash_for_request();

    if ($hash === '') { return ['device_id'=>'', 'device_name'=>'']; }

    $stmt = $pdo->prepare("SELECT device_id, device_name FROM odv_user_sessions WHERE token_hash=:hash LIMIT 1");

    $stmt->execute([':hash'=>$hash]);

    $row = $stmt->fetch();

    return $row ?: ['device_id'=>'', 'device_name'=>''];

}

function acquire_document_lock(PDO $pdo, array $user, string $uploadId): void

{

    ensure_security_tables($pdo);

    $pdo->prepare("DELETE FROM odv_document_locks WHERE expires_at < NOW()")->execute();

    $dev = current_session_device($pdo);

    $stmt = $pdo->prepare("SELECT * FROM odv_document_locks WHERE upload_id=:uid LIMIT 1");

    $stmt->execute([':uid'=>$uploadId]);

    $lock = $stmt->fetch();

    if ($lock && (int)$lock['locked_by_user_id'] !== (int)$user['id']) {

        $name = $lock['locked_by_name'] ?: 'einem anderen Benutzer';

        json_response(['success'=>false, 'error'=>"Dieses Dokument wird aktuell von {$name} bearbeitet."], 409);

    }

    $expires = date('Y-m-d H:i:s', time() + 15 * 60);

    $deviceId = (string)($dev['device_id'] ?? '');

    $deviceName = (string)($dev['device_name'] ?? '');

    $up = $pdo->prepare("REPLACE INTO odv_document_locks (upload_id, locked_by_user_id, locked_by_name, device_id, device_name, token_hash, locked_at, last_seen_at, expires_at) VALUES (:upload_id,:user_id,:name,:device_id,:device_name,:token_hash,COALESCE((SELECT locked_at FROM (SELECT locked_at FROM odv_document_locks WHERE upload_id=:upload_id2) x), NOW()),NOW(),:expires)");

    $up->execute([

        ':upload_id' => $uploadId,

        ':upload_id2' => $uploadId,

        ':user_id' => (int)$user['id'],

        ':name' => (string)$user['display_name'],

        ':device_id' => $deviceId,

        ':device_name' => $deviceName,

        ':token_hash' => get_token_hash_for_request(),

        ':expires' => $expires,

    ]);

}
