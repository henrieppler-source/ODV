<?php
declare(strict_types=1);

if (!function_exists('get_json_input')) {
    function get_json_input(): array
    {
        $raw = file_get_contents('php://input');
        if ($raw === false || trim($raw) === '') {
            return [];
        }
        $decoded = json_decode($raw, true);
        return is_array($decoded) ? $decoded : [];
    }
}

function api_log(string $level, string $message, array $context = []): void
{
    $logDir = __DIR__ . '/logs';
    if (!is_dir($logDir)) {
        @mkdir($logDir, 0750, true);
    }
    if (!is_dir($logDir) || !is_writable($logDir)) {
        return;
    }
    $sensitivePattern = '/(^|[_-])(password|passwd|token|secret|api[_-]?key|openai[_-]?api[_-]?key|authorization|dpapi)($|[_-])/i';
    $sanitize = static function ($value) use (&$sanitize, $sensitivePattern) {
        if (!is_array($value)) {
            return $value;
        }
        $out = [];
        foreach ($value as $key => $item) {
            $keyText = strtolower((string)$key);
            if (preg_match($sensitivePattern, $keyText)) {
                $out[$key] = '***';
            } else {
                $out[$key] = $sanitize($item);
            }
        }
        return $out;
    };
    $context = $sanitize($context);
    $line = json_encode([
        'time' => date('c'),
        'level' => $level,
        'message' => $message,
        'context' => $context,
        'ip' => $_SERVER['REMOTE_ADDR'] ?? null,
        'path' => $_SERVER['REQUEST_URI'] ?? null,
    ], JSON_UNESCAPED_UNICODE) . PHP_EOL;
    @file_put_contents($logDir . '/api.log', $line, FILE_APPEND | LOCK_EX);
}

function get_authorization_token(): ?string
{
    $headers = function_exists('getallheaders') ? getallheaders() : [];
    foreach ($headers as $name => $value) {
        if (strtolower($name) === 'authorization') {
            if (preg_match('/Bearer\s+(.+)/i', $value, $matches)) {
                return trim($matches[1]);
            }
        }
    }
    if (isset($_SERVER['HTTP_AUTHORIZATION'])) {
        if (preg_match('/Bearer\s+(.+)/i', $_SERVER['HTTP_AUTHORIZATION'], $matches)) {
            return trim($matches[1]);
        }
    }
    return null;
}

function create_token(): string
{
    return bin2hex(random_bytes(32));
}

function token_hash(string $token): string
{
    return hash('sha256', $token);
}

function current_user(): array
{
    $token = get_authorization_token();
    if (!$token) {
        json_response(['success' => false, 'error' => 'Nicht angemeldet'], 401);
    }

    $pdo = db();
    $stmt = $pdo->prepare("\n        SELECT\n            t.id AS token_id,\n            t.expires_at,\n            u.id,\n            u.username,\n            u.display_name,\n            u.role,\n            u.place,\n            u.is_active\n        FROM api_tokens t\n        INNER JOIN users u ON u.id = t.user_id\n        WHERE t.token_hash = :token_hash\n        LIMIT 1\n    ");
    $stmt->execute([':token_hash' => token_hash($token)]);
    $row = $stmt->fetch();

    if (!$row) {
        json_response(['success' => false, 'error' => 'Ungültiges Token'], 401);
    }
    if ((int)$row['is_active'] !== 1) {
        json_response(['success' => false, 'error' => 'Benutzer ist deaktiviert'], 403);
    }
    if (strtotime($row['expires_at']) < time()) {
        json_response(['success' => false, 'error' => 'Token abgelaufen'], 401);
    }

    $userForMaintenance = ['id' => (int)$row['id'], 'role' => $row['role'], 'display_name' => $row['display_name']];
    enforce_maintenance_for_user($pdo, $userForMaintenance);

    $update = $pdo->prepare("UPDATE api_tokens SET last_used_at = NOW() WHERE id = :id");
    $update->execute([':id' => $row['token_id']]);
    try {
        ensure_security_tables($pdo);
        $tokHash = token_hash($token);
        $sess = $pdo->prepare("UPDATE odv_user_sessions SET last_seen_at = NOW(), is_active = 1 WHERE token_hash = :token_hash AND ended_at IS NULL");
        $sess->execute([':token_hash' => $tokHash]);
    } catch (Throwable $e) {
        api_log('warning', 'Sitzung konnte nicht aktualisiert werden', ['error' => $e->getMessage()]);
    }

    return [
        'id' => (int)$row['id'],
        'username' => $row['username'],
        'display_name' => $row['display_name'],
        'email' => $row['email'] ?? null,
        'role' => $row['role'],
        'place' => $row['place'],
        'token_id' => (int)$row['token_id'],
    ];
}

function require_role(array $allowedRoles): array
{
    $user = current_user();
    $allowedRoles = array_map(static fn($r) => strtolower(trim((string)$r)), $allowedRoles);
    if (!in_array(role_key($user), $allowedRoles, true)) {
        api_log('warning', 'Berechtigung verweigert', ['user_id' => $user['id'], 'role' => $user['role']]);
        json_response(['success' => false, 'error' => 'Keine Berechtigung'], 403);
    }
    return $user;
}

function normalize_role(string $role): string
{
    $role = strtolower(trim($role));
    $allowed = ['ortschronist', 'admin', 'superadmin'];
    if (!in_array($role, $allowed, true)) {
        json_response(['success' => false, 'error' => 'Ungültige Rolle'], 400);
    }
    return $role;
}


function role_key(array $user): string
{
    return strtolower(trim((string)($user['role'] ?? '')));
}

function is_superadmin(array $user): bool
{
    return role_key($user) === 'superadmin';
}

function is_admin_role(array $user): bool
{
    return in_array(role_key($user), ['admin', 'superadmin'], true);
}

function folder_groups(): array
{
    return [
        '00_ORTSCHRONIK' => '00_ORTSCHRONIK',
        '01_ABLAGE_ORTSCHRONIK' => '01_ABLAGE_ORTSCHRONIK',
        '02_AUSTAUSCH' => '02_AUSTAUSCH',
        '03_INFORMATION' => '03_INFORMATION',
        '05_ORGA_CHRONISTEN' => '05_ORGA_CHRONISTEN',
        '06_UNSERE_ARBEITEN' => '06_UNSERE_ARBEITEN',
        'OWN_PLACE_FOLDER' => 'Eigener Ortsordner',
        'OTHER_PLACE_FOLDERS' => 'Andere Ortsordner',
    ];
}

function default_folder_permissions(string $role): array
{
    $role = strtolower($role);
    $all = [];
    foreach (array_keys(folder_groups()) as $key) {
        $all[$key] = ['can_read' => 1, 'can_write' => 1];
    }
    if (in_array($role, ['admin', 'superadmin'], true)) {
        return $all;
    }
    return [
        '00_ORTSCHRONIK' => ['can_read' => 1, 'can_write' => 0],
        '01_ABLAGE_ORTSCHRONIK' => ['can_read' => 1, 'can_write' => 1],
        '02_AUSTAUSCH' => ['can_read' => 1, 'can_write' => 1],
        '03_INFORMATION' => ['can_read' => 1, 'can_write' => 0],
        '05_ORGA_CHRONISTEN' => ['can_read' => 0, 'can_write' => 0],
        '06_UNSERE_ARBEITEN' => ['can_read' => 1, 'can_write' => 1],
        'OWN_PLACE_FOLDER' => ['can_read' => 1, 'can_write' => 1],
        'OTHER_PLACE_FOLDERS' => ['can_read' => 0, 'can_write' => 0],
    ];
}

function fetch_user_folder_permissions(PDO $pdo, int $userId, string $role): array
{
    $defaults = default_folder_permissions(strtolower(trim($role)));
    $stmt = $pdo->prepare("SELECT folder_group, can_read, can_write FROM user_folder_permissions WHERE user_id = :user_id");
    $stmt->execute([':user_id' => $userId]);
    foreach ($stmt->fetchAll() as $row) {
        $key = (string)$row['folder_group'];
        if (isset($defaults[$key])) {
            $defaults[$key] = ['can_read' => (int)$row['can_read'], 'can_write' => (int)$row['can_write']];
        }
    }
    $out = [];
    foreach (folder_groups() as $key => $label) {
        $out[] = [
            'folder_group' => $key,
            'label' => $label,
            'can_read' => (int)$defaults[$key]['can_read'],
            'can_write' => (int)$defaults[$key]['can_write'],
        ];
    }
    return $out;
}

function client_ip(): string
{
    return (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
}

function login_limit_check(PDO $pdo, string $username): void
{
    // Fallback: Wenn Migration noch nicht eingespielt ist, blockiert die API nicht.
    try {
        $ip = client_ip();
        $stmt = $pdo->prepare("\n            SELECT COUNT(*) AS cnt\n            FROM api_login_attempts\n            WHERE success = 0\n              AND attempted_at >= (NOW() - INTERVAL 15 MINUTE)\n              AND (username = :username OR ip_address = :ip)\n        ");
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
        $stmt = $pdo->prepare("\n            INSERT INTO api_login_attempts (username, ip_address, success)\n            VALUES (:username, :ip_address, :success)\n        ");
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
        $emails = array_values(array_unique(array_filter(array_map(static fn($r) => trim((string)$r['email']), $stmt->fetchAll()))));
        if (!$emails) { return; }
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

function build_nextcloud_remote_path(string $localFilePath, string $localNextcloudBase): string
{
    $file = trim(str_replace('\\', '/', $localFilePath));
    $base = trim(str_replace('\\', '/', $localNextcloudBase));
    if ($file === '') {
        return '';
    }
    if ($base !== '' && str_starts_with($file, $base)) {
        $relative = ltrim(substr($file, strlen($base)), '/');
        return $relative;
    }
    return ltrim($file, '/');
}

function send_text_mail(string $to, string $subject, string $body, array $attachments = []): bool
{
    $recipient = trim($to);
    if ($recipient === '') {
        return false;
    }
    $encodedSubject = mb_encode_mimeheader($subject, 'UTF-8', 'Q', "\r\n");
    $headers = [
        'MIME-Version: 1.0',
        'From: Ortschronik <noreply@ortschronik.info>',
    ];

    $cleanAttachments = [];
    foreach ($attachments as $attachment) {
        if (!is_array($attachment) || empty($attachment['content_base64'])) {
            continue;
        }
        $cleanAttachments[] = $attachment;
    }

    if ($cleanAttachments) {
        $boundary = '=_odv_' . bin2hex(random_bytes(12));
        $message = "This is a multi-part message in MIME format.\r\n";
        $message .= "--{$boundary}\r\n";
        $message .= "Content-Type: text/plain; charset=UTF-8\r\n";
        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";
        $message .= $body . "\r\n";
        foreach ($cleanAttachments as $attachment) {
            $filename = trim((string)($attachment['filename'] ?? 'Anhang'));
            $mime = trim((string)($attachment['mime_type'] ?? 'application/octet-stream'));
            $raw = base64_decode((string)$attachment['content_base64'], true);
            if ($raw === false) {
                continue;
            }
            $message .= "--{$boundary}\r\n";
            $message .= "Content-Type: {$mime}; name=\"" . str_replace('"', '\\"', $filename) . "\"\r\n";
            $message .= "Content-Transfer-Encoding: base64\r\n";
            $message .= "Content-Disposition: attachment; filename=\"" . str_replace('"', '\\"', $filename) . "\"\r\n\r\n";
            $message .= chunk_split(base64_encode($raw)) . "\r\n";
        }
        $message .= "--{$boundary}--\r\n";
        $headers[] = "Content-Type: multipart/mixed; boundary=\"{$boundary}\"";
        return mail($recipient, $encodedSubject, $message, implode("\r\n", $headers));
    }

    $headers[] = "Content-Type: text/plain; charset=UTF-8";
    $headers[] = "Content-Transfer-Encoding: 8bit";
    return mail($recipient, $encodedSubject, $body, implode("\r\n", $headers));
}

function create_nextcloud_public_share(string $remotePath): array
{
    $path = trim(str_replace('\\', '/', $remotePath));
    $pdo = db();
    $baseUrl = trim((string)(setting_get($pdo, 'nextcloud_web_files_url', '') ?? ''));
    if ($baseUrl === '') {
        $baseUrl = 'https://nx94165.your-storageshare.de/apps/files/files';
    }
    $baseUrl = rtrim($baseUrl, '/');
    if ($path === '') {
        return ['share_url' => $baseUrl, 'download_url' => $baseUrl, 'url' => $baseUrl];
    }
    $dir = '/' . trim(dirname($path), '.');
    if ($dir === '/' || $dir === '/.') {
        $dir = '/';
    }
    $link = $baseUrl . '?dir=' . rawurlencode($dir);
    return ['share_url' => $link, 'download_url' => $link, 'url' => $link];
}

function document_person_events_from_payload(array $document, array $persons): array
{
    $events = [];
    foreach ($persons as $person) {
        if (!is_array($person)) {
            continue;
        }
        $number = (int)($person['number'] ?? 0);
        $displayName = trim((string)($person['display_name'] ?? ''));
        if ($number <= 0 || $displayName === '') {
            continue;
        }
        $events[] = [
            'number' => $number,
            'display_name' => $displayName,
            'x' => isset($person['x']) ? (float)$person['x'] : null,
            'y' => isset($person['y']) ? (float)$person['y'] : null,
            'certainty' => isset($person['certainty']) ? (float)$person['certainty'] : null,
            'note' => trim((string)($person['note'] ?? '')),
        ];
    }
    return $events;
}

function add_person_points_for_document(PDO $pdo, int $documentId, string $uploadId, array $user, array $document, array $events): void
{
    add_person_points($pdo, $documentId, $uploadId, $user, $events);
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
    $up = $pdo->prepare("REPLACE INTO odv_document_locks (upload_id, locked_by_user_id, locked_by_name, device_id, device_name, token_hash, locked_at, last_seen_at, expires_at) VALUES (:upload_id,:user_id,:name,:device_id,:device_name,:token_hash,COALESCE((SELECT locked_at FROM (SELECT locked_at FROM odv_document_locks WHERE upload_id=:upload_id2) x), NOW()),NOW(),:expires)");
    $up->execute([':upload_id'=>$uploadId, ':upload_id2'=>$uploadId, ':user_id'=>(int)$user['id'], ':name'=>(string)$user['display_name'], ':device_id'=>$dev['device_id'] ?? '', ':device_name'=>$dev['device_name'] ?? '', ':token_hash'=>get_token_hash_for_request(), ':expires'=>$expires]);
}


function normalize_folder_token_api(string $value): string
{
    $text = mb_strtolower(trim($value), 'UTF-8');
    $text = str_replace(['ä','ö','ü','ß'], ['ae','oe','ue','ss'], $text);
    $text = preg_replace('/[^a-z0-9]+/u', '_', $text) ?? $text;
    return trim($text, '_');
}

function top_folder_from_path(string $path): string
{
    $path = str_replace('\\', '/', trim($path));
    if ($path === '') { return ''; }
    $parts = array_values(array_filter(explode('/', $path), static fn($p) => $p !== '' && $p !== '.'));
    foreach ($parts as $part) {
        if (preg_match('/^\d{2}_.+/', $part)) {
            return $part;
        }
    }
    return $parts[0] ?? '';
}

function load_place_folder_map(PDO $pdo): array
{
    $map = [];
    try {
        $rows = $pdo->query("SELECT place, folder_name FROM place_folders WHERE is_active = 1")->fetchAll();
        foreach ($rows as $row) {
            $map[normalize_folder_token_api((string)$row['place'])] = (string)$row['folder_name'];
        }
    } catch (Throwable $e) {
        // Migration fehlt evtl. noch; dann ohne Stammdaten fortfahren.
    }
    return $map;
}

function folder_group_from_path(PDO $pdo, array $user, string $path): ?string
{
    $top = top_folder_from_path($path);
    $topNorm = normalize_folder_token_api($top);
    $fixed = ['00_ORTSCHRONIK', '01_ABLAGE_ORTSCHRONIK', '02_AUSTAUSCH', '03_INFORMATION', '05_ORGA_CHRONISTEN', '06_UNSERE_ARBEITEN'];
    foreach ($fixed as $name) {
        if ($topNorm === normalize_folder_token_api($name)) {
            return $name;
        }
    }
    $placeNorm = normalize_folder_token_api((string)($user['place'] ?? ''));
    $placeFolders = load_place_folder_map($pdo);
    $ownFolder = $placeFolders[$placeNorm] ?? '';
    if ($ownFolder !== '' && $topNorm === normalize_folder_token_api($ownFolder)) {
        return 'OWN_PLACE_FOLDER';
    }
    if ($placeNorm !== '' && strpos($topNorm, $placeNorm) !== false) {
        return 'OWN_PLACE_FOLDER';
    }
    $known = array_map('normalize_folder_token_api', array_values($placeFolders));
    if (in_array($topNorm, $known, true)) {
        return 'OTHER_PLACE_FOLDERS';
    }
    if (preg_match('/^\d{2}_.+/', $top)) {
        return 'OTHER_PLACE_FOLDERS';
    }
    return null;
}

function user_has_folder_permission(PDO $pdo, array $user, string $path, string $mode): bool
{
    if (is_superadmin($user)) { return true; }
    $group = folder_group_from_path($pdo, $user, $path);
    if ($group === null) { return false; }
    $perms = fetch_user_folder_permissions($pdo, (int)$user['id'], role_key($user));
    foreach ($perms as $perm) {
        if (($perm['folder_group'] ?? '') === $group) {
            return (bool)((int)($perm[$mode === 'write' ? 'can_write' : 'can_read'] ?? 0));
        }
    }
    return false;
}

function allowed_status_values(): array
{
    return ['hochgeladen', 'rueckfrage', 'geprueft', 'uebernommen', 'archiviert'];
}

function canonical_document_status(string $status): string
{
    $status = trim($status);
    return $status;
}

function validate_document_status(string $status): string
{
    $status = canonical_document_status($status);
    if (!in_array($status, allowed_status_values(), true)) {
        json_response([
            'success' => false,
            'error' => 'Ungültiger Status',
            'allowed' => allowed_status_values()
        ], 400);
    }
    return $status;
}

function document_permission_path(array $document): string
{
    $path = trim((string)($document['target_folder'] ?? ''));
    if ($path !== '') { return $path; }
    return trim((string)($document['current_path'] ?? ''));
}

function ensure_document_read_permission(PDO $pdo, array $user, array $document): void
{
    if (is_superadmin($user)) { return; }
    $path = document_permission_path($document);
    $isOwner = ((int)($document['uploaded_by_user_id'] ?? 0) === (int)($user['id'] ?? 0));
    if ($isOwner) { return; }
    if ($path !== '' && user_has_folder_permission($pdo, $user, $path, 'read')) { return; }
    json_response(['success' => false, 'error' => 'Keine Leseberechtigung für dieses Dokument'], 403);
}

function ensure_document_write_permission(PDO $pdo, array $user, array $documentOrInput): void
{
    if (is_superadmin($user)) { return; }
    $path = document_permission_path($documentOrInput);
    $isOwner = ((int)($documentOrInput['uploaded_by_user_id'] ?? 0) === (int)($user['id'] ?? 0));
    if ($isOwner) { return; }
    if ($path !== '' && user_has_folder_permission($pdo, $user, $path, 'write')) { return; }
    json_response(['success' => false, 'error' => 'Keine Schreibberechtigung für dieses Dokument bzw. diesen Zielordner'], 403);
}


function current_points_year(): int
{
    return (int)date('Y');
}

function ensure_point_year_closures_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS point_year_closures (
        year INT PRIMARY KEY,
        closed_at DATETIME DEFAULT NULL,
        closed_by_user_id INT DEFAULT NULL,
        note TEXT DEFAULT NULL,
        CONSTRAINT fk_point_year_closed_by FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

function points_year_budget_key(int $year): string
{
    return 'points_year_budget_' . $year;
}

function point_year_closure(PDO $pdo, int $year): ?array
{
    ensure_point_year_closures_table($pdo);
    $stmt = $pdo->prepare("\n        SELECT pyc.year, pyc.closed_at, pyc.closed_by_user_id, pyc.note, u.display_name AS closed_by_name\n        FROM point_year_closures pyc\n        LEFT JOIN users u ON u.id = pyc.closed_by_user_id\n        WHERE pyc.year = :year\n        LIMIT 1\n    ");
    $stmt->execute([':year' => $year]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function point_year_is_closed(PDO $pdo, int $year): bool
{
    return point_year_closure($pdo, $year) !== null;
}

function points_year_budget(PDO $pdo, int $year): float
{
    $value = setting_get($pdo, points_year_budget_key($year), null);
    if ($value === null || trim($value) === '') {
        return 0.0;
    }
    return (float)str_replace(',', '.', (string)$value);
}

function points_year_total(PDO $pdo, int $year): array
{
    $stmt = $pdo->prepare("\n        SELECT\n            COALESCE(SUM(cp.points), 0) AS total_points,\n            COUNT(DISTINCT cp.user_id) AS participant_count\n        FROM contribution_points cp\n        LEFT JOIN documents d ON d.id = cp.document_id\n        WHERE cp.points_year = :year\n          AND cp.is_confirmed = 1\n          AND (d.status = 'uebernommen' OR cp.is_manual = 1)\n    ");
    $stmt->execute([':year' => $year]);
    $row = $stmt->fetch();
    return [
        'total_points' => (int)($row['total_points'] ?? 0),
        'participant_count' => (int)($row['participant_count'] ?? 0),
    ];
}

function require_points_year_editable(PDO $pdo, int $year): void
{
    if (point_year_is_closed($pdo, $year)) {
        json_response(['success' => false, 'error' => 'Das Punktejahr ist abgeschlossen und kann nicht mehr geändert werden.'], 409);
    }
}

function point_rule_points(PDO $pdo, int $year, string $ruleKey, int $default = 0): int
{
    $stmt = $pdo->prepare("SELECT points FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");
    $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);
    $row = $stmt->fetch();
    return $row ? (int)$row['points'] : $default;
}

function point_rule_key_for_field_category(PDO $pdo, int $year, string $field, string $category, string $fallback): string
{
    $candidates = [$field . '_' . $category];
    if ($category === 'metadata') {
        $candidates[] = $field . '_metadaten';
    }
    $candidates[] = $fallback;
    foreach (array_values(array_unique($candidates)) as $ruleKey) {
        $stmt = $pdo->prepare("SELECT rule_key FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");
        $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);
        $row = $stmt->fetch();
        if ($row) {
            return (string)$row['rule_key'];
        }
    }
    return $fallback;
}

function metadata_point_rule_catalog(): array
{
    return [
        'description' => ['label' => 'Aussagekräftige Beschreibung', 'check_type' => 'characters', 'min_value' => 50],
        'keywords' => ['label' => 'Stichwörter vergeben', 'check_type' => 'count', 'min_value' => 3],
        'source' => ['label' => 'Quelle/Herkunft angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'usage_permission' => ['label' => 'Nutzungsfreigabe geklärt', 'check_type' => 'characters', 'min_value' => 3],
        'rights_note' => ['label' => 'Rechtehinweis angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'copyright_author' => ['label' => 'Urheber angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'rights_holder' => ['label' => 'Rechteinhaber angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'archive_name' => ['label' => 'Archiv/Bestand angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'archive_signature' => ['label' => 'Archivsignatur angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'document_date' => ['label' => 'Datum/Zeitraum angegeben', 'check_type' => 'characters', 'min_value' => 3],
        'event' => ['label' => 'Ereignis/Thema zugeordnet', 'check_type' => 'characters', 'min_value' => 3],
    ];
}

function metadata_point_rule_key(string $field, string $source): string
{
    return trim($field) . '_' . ($source === 'openAI' ? 'openAI' : 'manual');
}

function point_rule_config(PDO $pdo, int $year, string $ruleKey): ?array
{
    $stmt = $pdo->prepare("SELECT * FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");
    $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function normalize_point_path(string $path): string
{
    return strtolower(str_replace('\\', '/', $path));
}

function is_point_eligible_path(string $path): bool
{
    $path = '/' . trim(normalize_point_path($path), '/') . '/';
    if ($path === '//') { return false; }
    $eligible = [
        '00_ortschronik',
        '01_ablage_ortschronik',
        '06_unsere_arbeiten',
        '06_arbeit_der_ortschronisten',
        '06_arbeiten_der_ortschronisten'
    ];
    foreach ($eligible as $folder) {
        if (str_contains($path, '/' . $folder . '/')) { return true; }
    }
    return false;
}

function normalized_path_words(string $path): string
{
    $text = normalize_point_path($path);
    $text = str_replace(['ä', 'ö', 'ü', 'ß'], ['ae', 'oe', 'ue', 'ss'], $text);
    $text = preg_replace('/[^a-z0-9]+/u', ' ', $text) ?? $text;
    return trim($text);
}

function special_collection_for_document_path(string $targetFolder, string $currentPath): ?string
{
    $haystack = normalized_path_words($targetFolder . ' ' . $currentPath);
    if (str_contains($haystack, 'kinder wie die zeit vergeht')) {
        return 'kinder_wie_die_zeit_vergeht';
    }
    if (str_contains($haystack, 'jahresblatt') || str_contains($haystack, 'jahresblaetter')) {
        return 'jahresblaetter';
    }
    return null;
}

function add_special_collection_points(PDO $pdo, int $documentId, string $uploadId, array $user, string $targetFolder, string $currentPath, string $captureMode): void
{
    $collection = special_collection_for_document_path($targetFolder, $currentPath);
    if ($collection === null) {
        return;
    }
    $isExistingMetadata = ($captureMode === 'existing_file_metadata');
    $year = current_points_year();
    $points = point_rule_points($pdo, $year, 'special_collection', 10);
    $ruleKey = 'special_collection';
    if ($collection === 'kinder_wie_die_zeit_vergeht') {
        $reason = $isExistingMetadata ? 'Kinder wie die Zeit vergeht: nachträgliche Metadatenerfassung' : 'Kinder wie die Zeit vergeht: neu über ODV abgelegt';
    } else {
        $reason = $isExistingMetadata ? 'Jahresblätter: nachträgliche Metadatenerfassung' : 'Jahresblätter: neu über ODV abgelegt';
    }
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'special_collection', $ruleKey, $reason, 'current_path', $points, false);
}


function db_table_exists(PDO $pdo, string $tableName): bool
{
    static $cache = [];
    $key = strtolower($tableName);
    if (array_key_exists($key, $cache)) {
        return $cache[$key];
    }
    try {
        $stmt = $pdo->prepare("SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name");
        $stmt->execute([':table_name' => $tableName]);
        $cache[$key] = ((int)$stmt->fetchColumn()) > 0;
    } catch (Throwable $e) {
        $cache[$key] = false;
    }
    return $cache[$key];
}


function ensure_mail_history_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS mail_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        sent_by_user_id INT DEFAULT NULL,
        sent_by_name VARCHAR(255) DEFAULT NULL,
        recipient_email VARCHAR(255) NOT NULL,
        subject VARCHAR(255) NOT NULL,
        body_preview TEXT DEFAULT NULL,
        mode VARCHAR(50) DEFAULT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'sent',
        error_message TEXT DEFAULT NULL,
        documents_json LONGTEXT DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_mail_history_sent_at (sent_at),
        INDEX idx_mail_history_recipient (recipient_email),
        INDEX idx_mail_history_sender (sent_by_user_id)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function db_column_exists(PDO $pdo, string $tableName, string $columnName): bool
{
    static $cache = [];
    $key = strtolower($tableName . '.' . $columnName);
    if (array_key_exists($key, $cache)) {
        return $cache[$key];
    }
    try {
        $stmt = $pdo->prepare("SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name AND COLUMN_NAME = :column_name");
        $stmt->execute([':table_name' => $tableName, ':column_name' => $columnName]);
        $cache[$key] = ((int)$stmt->fetchColumn()) > 0;
    } catch (Throwable $e) {
        $cache[$key] = false;
    }
    return $cache[$key];
}

function ensure_point_rules_model_columns(PDO $pdo): void
{
    $columns = [
        'rule_type' => "ALTER TABLE point_rules ADD COLUMN rule_type VARCHAR(40) NOT NULL DEFAULT 'metadata' AFTER category",
        'source_field' => "ALTER TABLE point_rules ADD COLUMN source_field VARCHAR(120) DEFAULT NULL AFTER rule_type",
        'evaluation_source' => "ALTER TABLE point_rules ADD COLUMN evaluation_source VARCHAR(30) DEFAULT NULL AFTER source_field",
        'check_type' => "ALTER TABLE point_rules ADD COLUMN check_type VARCHAR(30) NOT NULL DEFAULT 'none' AFTER evaluation_source",
        'min_value' => "ALTER TABLE point_rules ADD COLUMN min_value INT NOT NULL DEFAULT 0 AFTER check_type",
        'is_system' => "ALTER TABLE point_rules ADD COLUMN is_system TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active",
    ];
    foreach ($columns as $column => $sql) {
        if (!db_column_exists($pdo, 'point_rules', $column)) {
            $pdo->exec($sql);
        }
    }
}

function ensure_points_schema_available(PDO $pdo): void
{
    $missing = [];
    foreach (['documents', 'contribution_points', 'point_rules', 'document_history'] as $tableName) {
        if (!db_table_exists($pdo, $tableName)) {
            $missing[] = 'Tabelle ' . $tableName;
        }
    }
    foreach ([
        ['documents', 'keywords'],
        ['documents', 'transcription_done'],
        ['documents', 'transcription_type'],
        ['documents', 'transcription_note'],
        ['documents', 'points_eligible'],
        ['contribution_points', 'document_id'],
        ['contribution_points', 'points_year'],
        ['contribution_points', 'rule_key'],
        ['contribution_points', 'source_field'],
        ['contribution_points', 'is_manual'],
        ['contribution_points', 'is_confirmed'],
    ] as $pair) {
        if (!db_column_exists($pdo, $pair[0], $pair[1])) {
            $missing[] = 'Spalte ' . $pair[0] . '.' . $pair[1];
        }
    }
    if ($missing) {
        throw new RuntimeException('Punkte-Datenbankschema unvollständig. Bitte SQL-Migrationen v48/v49/v51/v55 prüfen. Fehlend: ' . implode(', ', $missing));
    }
    ensure_point_rules_model_columns($pdo);
}

function is_point_eligible_document(array $document): bool
{
    if (array_key_exists('points_eligible', $document) && $document['points_eligible'] !== null && $document['points_eligible'] !== '') {
        return ((int)$document['points_eligible']) === 1;
    }
    return is_point_eligible_path((string)($document['target_folder'] ?? '')) || is_point_eligible_path((string)($document['current_path'] ?? ''));
}

function document_context_for_points(PDO $pdo, int $documentId): ?array
{
    $hasPointsEligible = db_column_exists($pdo, 'documents', 'points_eligible');
    $sql = $hasPointsEligible
        ? "SELECT id, original_filename, stored_filename, current_filename, document_type, target_folder, current_path, points_eligible FROM documents WHERE id = :id LIMIT 1"
        : "SELECT id, original_filename, stored_filename, current_filename, document_type, target_folder, current_path, 0 AS points_eligible FROM documents WHERE id = :id LIMIT 1";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([':id' => $documentId]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function is_image_document_context(array $document): bool
{
    $type = strtolower((string)($document['document_type'] ?? ''));
    if (str_contains($type, 'bild') || str_contains($type, 'foto') || str_contains($type, 'photo') || str_contains($type, 'image')) {
        return true;
    }
    $name = strtolower((string)($document['current_filename'] ?? $document['stored_filename'] ?? $document['original_filename'] ?? $document['current_path'] ?? ''));
    return (bool)preg_match('/\.(jpe?g|png|gif|bmp|tiff?|webp)$/i', $name);
}


function points_description_is_eligible(string $text): bool
{
    $text = trim($text);
    if (function_exists('mb_strlen')) {
        return mb_strlen($text, 'UTF-8') >= 50;
    }
    return strlen($text) >= 50;
}

function points_keyword_count(string $text): int
{
    $parts = preg_split('/[;,]+/u', $text);
    $count = 0;
    if (is_array($parts)) {
        foreach ($parts as $part) {
            if (trim((string)$part) !== '') {
                $count++;
            }
        }
    }
    return $count;
}

function points_value_matches_rule(string $field, string $value, string $checkType, int $minValue): bool
{
    $value = trim($value);
    if ($value === '') {
        return false;
    }
    if ($checkType === 'none') {
        return true;
    }
    if ($checkType === 'words') {
        $words = preg_split('/\s+/u', $value, -1, PREG_SPLIT_NO_EMPTY);
        return count($words ?: []) >= max(1, $minValue);
    }
    if ($checkType === 'count') {
        return points_keyword_count($value) >= max(1, $minValue);
    }
    $length = function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
    return $length >= max(1, $minValue);
}

function points_metadata_field_is_eligible(PDO $pdo, int $year, string $field, string $source, string $value): bool
{
    $catalog = metadata_point_rule_catalog();
    $default = $catalog[$field] ?? ['check_type' => 'characters', 'min_value' => 1];
    $rule = point_rule_config($pdo, $year, metadata_point_rule_key($field, $source));
    if (!$rule) {
        return false;
    }
    return points_value_matches_rule(
        $field,
        $value,
        (string)($rule['check_type'] ?? $default['check_type']),
        (int)($rule['min_value'] ?? $default['min_value'])
    );
}

function add_contribution_point(PDO $pdo, int $documentId, string $uploadId, array $beneficiary, array $createdBy, string $category, string $ruleKey, string $reason, string $sourceField, int $points, bool $manual = false): void
{
    if ($points <= 0) {
        return;
    }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_point_eligible_document($documentContext)) {
        return;
    }
    $year = (int)date('Y');
    if (point_year_is_closed($pdo, $year)) {
        api_log('warning', 'Punktevergabe blockiert, Jahr ist abgeschlossen', ['document_id' => $documentId, 'upload_id' => $uploadId, 'rule_key' => $ruleKey, 'year' => $year]);
        return;
    }
    try {
        $stmt = $pdo->prepare("\n            INSERT INTO contribution_points (document_id, upload_id, user_id, user_display_name, points_year, category, rule_key, reason, source_field, points, created_by_user_id, created_by_name, is_manual, is_confirmed)\n            VALUES (:document_id, :upload_id, :user_id, :user_display_name, :points_year, :category, :rule_key, :reason, :source_field, :points, :created_by_user_id, :created_by_name, :is_manual, 1)\n        ");
        $stmt->execute([
            ':document_id' => $documentId,
            ':upload_id' => $uploadId,
            ':user_id' => (int)$beneficiary['id'],
            ':user_display_name' => (string)$beneficiary['display_name'],
            ':points_year' => $year,
            ':category' => $category,
            ':rule_key' => $ruleKey,
            ':reason' => $reason,
            ':source_field' => $sourceField,
            ':points' => $points,
            ':created_by_user_id' => (int)$createdBy['id'],
            ':created_by_name' => (string)$createdBy['display_name'],
            ':is_manual' => $manual ? 1 : 0,
        ]);
    } catch (PDOException $e) {
        // Dubletten sind durch den Unique-Key möglich und sollen keine Bearbeitung blockieren.
        if ((int)$e->getCode() !== 23000) {
            throw $e;
        }
    }
}


function text_change_size(string $old, string $new): int
{
    $old = trim($old);
    $new = trim($new);
    if ($old === $new) { return 0; }
    $oldLen = function_exists('mb_strlen') ? mb_strlen($old, 'UTF-8') : strlen($old);
    $newLen = function_exists('mb_strlen') ? mb_strlen($new, 'UTF-8') : strlen($new);
    return max(abs($newLen - $oldLen), levenshtein(substr($old, 0, 255), substr($new, 0, 255)));
}

function remove_own_auto_points_for_field(PDO $pdo, int $documentId, int $userId, string $ruleKey, string $sourceField): void
{
    if ($userId <= 0) { return; }
    $stmt = $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND user_id = :user_id AND rule_key = :rule_key AND source_field = :source_field AND is_manual = 0");
    $stmt->execute([':document_id' => $documentId, ':user_id' => $userId, ':rule_key' => $ruleKey, ':source_field' => $sourceField]);
}

function remove_auto_points_for_field(PDO $pdo, int $documentId, string $ruleKey, string $sourceField): void
{
    $stmt = $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND rule_key = :rule_key AND source_field = :source_field AND is_manual = 0");
    $stmt->execute([':document_id' => $documentId, ':rule_key' => $ruleKey, ':source_field' => $sourceField]);
}

function add_correction_point_if_relevant(PDO $pdo, int $documentId, string $uploadId, array $user, string $field, string $old, string $new): void
{
    $delta = text_change_size($old, $new);
    if ($delta <= 30) { return; }
    $year = current_points_year();
    $ruleKey = 'metadata_correction_' . $field;
    $sourceField = $field . '_correction';
    if (point_exists_for_document_rule($pdo, $documentId, $ruleKey, $sourceField, false)) { return; }
    $points = point_rule_points($pdo, $year, 'metadata_correction', 1);
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $ruleKey, 'Fachliche Korrektur/Ergänzung: ' . $field, $sourceField, $points, false);
}

function add_auto_points_for_metadata(PDO $pdo, int $documentId, string $uploadId, array $user, array $values, ?array $oldValues = null, array $openaiFields = []): void
{
    $year = current_points_year();
    $openaiFields = array_values(array_unique(array_filter(array_map(static fn($field) => trim((string)$field), $openaiFields))));
    $openaiFieldSet = array_fill_keys($openaiFields, true);
    $rules = metadata_point_rule_catalog();
    foreach ($rules as $field => $info) {
        $new = trim((string)($values[$field] ?? ''));
        $old = $oldValues === null ? '' : trim((string)($oldValues[$field] ?? ''));
        $openAiRuleKey = metadata_point_rule_key($field, 'openAI');
        $manualRuleKey = metadata_point_rule_key($field, 'manual');
        $newOpenAiEligible = isset($openaiFieldSet[$field]) && $old === '' && points_metadata_field_is_eligible($pdo, $year, $field, 'openAI', $new);
        $newManualEligible = !$newOpenAiEligible && points_metadata_field_is_eligible($pdo, $year, $field, 'manual', $new);
        if ($newOpenAiEligible) {
            $points = point_rule_points($pdo, $year, $openAiRuleKey, 1);
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $openAiRuleKey, $info['label'], $field, $points, false);
        } elseif ($newManualEligible) {
            remove_auto_points_for_field($pdo, $documentId, $openAiRuleKey, $field);
            $points = point_rule_points($pdo, $year, $manualRuleKey, 2);
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $manualRuleKey, $info['label'], $field, $points, false);
        } else {
            remove_auto_points_for_field($pdo, $documentId, $openAiRuleKey, $field);
            remove_auto_points_for_field($pdo, $documentId, $manualRuleKey, $field);
        }
    }
    $transDone = (bool)($values['transcription_done'] ?? false);
    $oldTransDone = $oldValues === null ? false : (bool)($oldValues['transcription_done'] ?? false);
    if ($transDone && !$oldTransDone) {
        $type = strtolower(trim((string)($values['transcription_type'] ?? '')));
        $rule = 'transcription_short'; $default = 3; $label = 'Transkription / Abschrift erstellt';
        if (str_contains($type, 'schwierig') || str_contains($type, 'handschrift')) { $rule = 'transcription_difficult'; $default = 8; $label = 'Schwierige Transkription'; }
        elseif (str_contains($type, 'zeitung') || str_contains($type, 'akte') || str_contains($type, 'urkunde')) { $rule = 'transcription_document'; $default = 10; $label = 'Transkription Zeitung / Akte / Urkunde'; }
        elseif (str_contains($type, 'voll')) { $rule = 'transcription_full'; $default = 5; $label = 'Vollständige Transkription'; }
        $points = point_rule_points($pdo, $year, $rule, $default);
        add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $rule, $label, 'transcription_done', $points, false);
    }
}

function add_person_points(PDO $pdo, int $documentId, string $uploadId, array $user, array $persons): void
{
    $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND category = 'persons' AND is_manual = 0")->execute([':document_id' => $documentId]);
    if (count($persons) <= 0) {
        return;
    }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_image_document_context($documentContext)) {
        return;
    }
    $year = current_points_year();
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'persons', 'persons_image_marked', 'Bild mit Personenmarkierungen', 'persons_image', point_rule_points($pdo, $year, 'persons_image_marked', 5), false);
    $index = 0;
    foreach ($persons as $person) {
        if (is_array($person)) {
            $index++;
            $number = (int)($person['number'] ?? $index);
            if ($number <= 0) { $number = $index; }
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'persons', 'persons_per_person', 'Personenmarkierung je Person', 'person_' . $number, point_rule_points($pdo, $year, 'persons_per_person', 1), false);
        }
    }
}

function point_user_array(int $id, string $displayName): array
{
    return ['id' => $id, 'display_name' => $displayName !== '' ? $displayName : ('Benutzer ' . $id)];
}

function document_uploader_for_points(array $doc): array
{
    return point_user_array((int)($doc['uploaded_by_user_id'] ?? 0), (string)($doc['uploaded_by_name'] ?? $doc['uploaded_by_display_name'] ?? ''));
}

function point_exists_for_document_rule(PDO $pdo, int $documentId, string $ruleKey, string $sourceField, bool $manual = false): bool
{
    $stmt = $pdo->prepare("SELECT id FROM contribution_points WHERE document_id = :document_id AND rule_key = :rule_key AND COALESCE(source_field, '') = :source_field AND is_manual = :is_manual LIMIT 1");
    $stmt->execute([
        ':document_id' => $documentId,
        ':rule_key' => $ruleKey,
        ':source_field' => $sourceField,
        ':is_manual' => $manual ? 1 : 0,
    ]);
    return (bool)$stmt->fetch();
}

function point_rule_source_field_from_key(string $ruleKey): string
{
    $key = trim($ruleKey);
    if ($key === '') { return 'manual_bonus'; }
    foreach (['_metadata', '_metadaten', '_manual'] as $suffix) {
        if (str_ends_with($key, $suffix)) {
            $key = substr($key, 0, -strlen($suffix));
            break;
        }
    }
    $aliases = [
        'metadata_description' => 'description',
        'metadata_keywords' => 'keywords',
        'metadata_source' => 'source',
        'rights_author' => 'copyright_author',
        'rights_usage_permission' => 'usage_permission',
        'event_topic' => 'event',
        'archive_signature' => 'archive_signature',
        'rights_holder' => 'rights_holder',
        'rights_note' => 'rights_note',
        'document_date' => 'document_date',
        'archive_name' => 'archive_name',
        'openai_metadata' => 'openai_metadata',
    ];
    return $aliases[$key] ?? $key;
}

function add_contribution_point_retro(PDO $pdo, int $documentId, string $uploadId, array $beneficiary, array $createdBy, string $category, string $ruleKey, string $reason, string $sourceField, int $points): string
{
    if ($points <= 0) { return 'skipped_zero'; }
    if ((int)($beneficiary['id'] ?? 0) <= 0) { return 'skipped_no_user'; }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_point_eligible_document($documentContext)) { return 'skipped_ineligible'; }
    if (point_year_is_closed($pdo, current_points_year())) { return 'skipped_closed'; }
    if (point_exists_for_document_rule($pdo, $documentId, $ruleKey, $sourceField, false)) { return 'existing'; }
    add_contribution_point($pdo, $documentId, $uploadId, $beneficiary, $createdBy, $category, $ruleKey, $reason, $sourceField, $points, false);
    return 'created';
}

function metadata_field_beneficiary(PDO $pdo, array $doc, string $field): array
{
    try {
        $stmt = $pdo->prepare("\n            SELECT user_id, user_display_name\n            FROM document_history\n            WHERE document_id = :document_id\n              AND action = 'document_updated'\n              AND details = :details\n              AND (old_value IS NULL OR old_value = '')\n              AND new_value IS NOT NULL AND new_value <> ''\n              AND user_id IS NOT NULL AND user_id > 0\n            ORDER BY created_at ASC, id ASC\n            LIMIT 1\n        ");
        $stmt->execute([':document_id' => (int)$doc['id'], ':details' => 'Feld geändert: ' . $field]);
        $row = $stmt->fetch();
        if ($row) {
            return point_user_array((int)$row['user_id'], (string)$row['user_display_name']);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Punkte-Nachberechnung: Feld-Historie konnte nicht ausgewertet werden', ['document_id' => $doc['id'] ?? null, 'field' => $field, 'error' => $e->getMessage()]);
    }
    return document_uploader_for_points($doc);
}

function admin_review_beneficiary(PDO $pdo, array $doc, string $field, string $newValue): ?array
{
    try {
        $stmt = $pdo->prepare("\n            SELECT user_id, user_display_name\n            FROM document_history\n            WHERE document_id = :document_id\n              AND action = 'document_updated'\n              AND details = :details\n              AND new_value = :new_value\n              AND user_id IS NOT NULL AND user_id > 0\n            ORDER BY created_at ASC, id ASC\n            LIMIT 1\n        ");
        $stmt->execute([':document_id' => (int)$doc['id'], ':details' => 'Feld geändert: ' . $field, ':new_value' => $newValue]);
        $row = $stmt->fetch();
        if ($row) {
            return point_user_array((int)$row['user_id'], (string)$row['user_display_name']);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Punkte-Nachberechnung: Admin-Historie konnte nicht ausgewertet werden', ['document_id' => $doc['id'] ?? null, 'field' => $field, 'error' => $e->getMessage()]);
    }
    return null;
}

function recalculate_points_for_document(PDO $pdo, array $doc, array $currentUser): array
{
    $stats = ['created' => 0, 'existing' => 0, 'skipped_ineligible' => 0, 'skipped_no_user' => 0, 'skipped_zero' => 0, 'skipped_closed' => 0];
    $documentId = (int)$doc['id'];
    $uploadId = (string)$doc['upload_id'];
    if (!is_point_eligible_document($doc)) {
        $stats['skipped_ineligible']++;
        return $stats;
    }
    $year = current_points_year();
    $rules = metadata_point_rule_catalog();
    foreach ($rules as $field => $info) {
        if (!points_metadata_field_is_eligible($pdo, $year, $field, 'manual', (string)($doc[$field] ?? ''))) { continue; }
        $beneficiary = metadata_field_beneficiary($pdo, $doc, $field);
        $ruleKey = metadata_point_rule_key($field, 'manual');
        $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'metadata', $ruleKey, $info['label'], $field, point_rule_points($pdo, $year, $ruleKey, 2));
        $stats[$result] = ($stats[$result] ?? 0) + 1;
    }
    if ((int)($doc['transcription_done'] ?? 0) === 1) {
        $type = strtolower(trim((string)($doc['transcription_type'] ?? '')));
        $rule = 'transcription_short'; $default = 3; $label = 'Transkription / Abschrift erstellt';
        if (str_contains($type, 'schwierig') || str_contains($type, 'handschrift')) { $rule = 'transcription_difficult'; $default = 8; $label = 'Schwierige Transkription'; }
        elseif (str_contains($type, 'zeitung') || str_contains($type, 'akte') || str_contains($type, 'urkunde')) { $rule = 'transcription_document'; $default = 10; $label = 'Transkription Zeitung / Akte / Urkunde'; }
        elseif (str_contains($type, 'voll')) { $rule = 'transcription_full'; $default = 5; $label = 'Vollständige Transkription'; }
        $beneficiary = metadata_field_beneficiary($pdo, $doc, 'transcription_done');
        $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'metadata', $rule, $label, 'transcription_done', point_rule_points($pdo, $year, $rule, $default));
        $stats[$result] = ($stats[$result] ?? 0) + 1;
    }
    $persons = [];
    if (db_table_exists($pdo, 'document_persons')) {
        try {
            $personColumns = "number, display_name";
            $personColumns .= db_column_exists($pdo, 'document_persons', 'created_by_user_id') ? ", created_by_user_id" : ", NULL AS created_by_user_id";
            $personColumns .= db_column_exists($pdo, 'document_persons', 'created_by_name') ? ", created_by_name" : ", NULL AS created_by_name";
            $pstmt = $pdo->prepare("SELECT " . $personColumns . " FROM document_persons WHERE document_id = :document_id");
            $pstmt->execute([':document_id' => $documentId]);
            $persons = $pstmt->fetchAll();
        } catch (Throwable $e) {
            api_log('warning', 'Punkte-Nachberechnung: Personen konnten nicht ausgewertet werden', ['document_id' => $documentId, 'error' => $e->getMessage()]);
            $persons = [];
        }
    }
    if (count($persons) > 0) {
        $personBeneficiary = null;
        foreach ($persons as $p) {
            if ((int)($p['created_by_user_id'] ?? 0) > 0) { $personBeneficiary = point_user_array((int)$p['created_by_user_id'], (string)($p['created_by_name'] ?? '')); break; }
        }
        if (!$personBeneficiary) { $personBeneficiary = document_uploader_for_points($doc); }
        if (is_image_document_context($doc)) {
            $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $personBeneficiary, $currentUser, 'persons', 'persons_image_marked', 'Bild mit Personenmarkierungen', 'persons_image', point_rule_points($pdo, $year, 'persons_image_marked', 5));
            $stats[$result] = ($stats[$result] ?? 0) + 1;
            $index = 0;
            foreach ($persons as $p) {
                $index++;
                $number = (int)($p['number'] ?? $index);
                if ($number <= 0) { $number = $index; }
                $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $personBeneficiary, $currentUser, 'persons', 'persons_per_person', 'Personenmarkierung je Person', 'person_' . $number, point_rule_points($pdo, $year, 'persons_per_person', 1));
                $stats[$result] = ($stats[$result] ?? 0) + 1;
            }
        }
    }
    if ((string)($doc['status'] ?? '') === 'uebernommen') {
        $beneficiary = admin_review_beneficiary($pdo, $doc, 'status', 'uebernommen');
        if ($beneficiary) {
            $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'admin_review', 'admin_review_accepted', 'Dokument geprüft und übernommen', 'status', point_rule_points($pdo, $year, 'admin_review_accepted', 1));
            $stats[$result] = ($stats[$result] ?? 0) + 1;
        }
    }
    return $stats;
}

function merge_point_stats(array $base, array $add): array
{
    foreach ($add as $key => $value) {
        $base[$key] = ($base[$key] ?? 0) + (int)$value;
    }
    return $base;
}


function ensure_system_settings_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS system_settings (
        setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
        setting_value TEXT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

function setting_get(PDO $pdo, string $key, ?string $default = null): ?string
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1");
    $stmt->execute([':k' => $key]);
    $value = $stmt->fetchColumn();
    return $value === false ? $default : (string)$value;
}

function setting_set(PDO $pdo, string $key, string $value): void
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("INSERT INTO system_settings (setting_key, setting_value) VALUES (:k, :v)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_at = NOW()");
    $stmt->execute([':k' => $key, ':v' => $value]);
}

function setting_delete(PDO $pdo, string $key): void
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("DELETE FROM system_settings WHERE setting_key = :k");
    $stmt->execute([':k' => $key]);
}

function operating_mode(PDO $pdo): string
{
    $mode = strtolower(trim((string)setting_get($pdo, 'operating_mode', 'production')));
    return $mode === 'test' ? 'test' : 'production';
}

function operating_mode_label(string $mode): string
{
    return $mode === 'test' ? 'Testbetrieb' : 'Produktivbetrieb';
}


function ensure_manual_special_points_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS manual_special_points (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        user_display_name VARCHAR(200) NOT NULL,
        points_year INT NOT NULL,
        activity_date DATE DEFAULT NULL,
        rule_key VARCHAR(120) NOT NULL,
        rule_label VARCHAR(255) NOT NULL,
        hours DECIMAL(8,2) DEFAULT NULL,
        points INT NOT NULL,
        reason TEXT NOT NULL,
        note TEXT DEFAULT NULL,
        created_by_user_id INT DEFAULT NULL,
        created_by_name VARCHAR(200) DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_msp_year (points_year),
        INDEX idx_msp_user_year (user_id, points_year),
        INDEX idx_msp_created_by (created_by_user_id),
        CONSTRAINT fk_msp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_msp_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function maintenance_state(PDO $pdo): array
{
    $enabled = setting_get($pdo, 'maintenance_enabled', '0') === '1';
    $startsAt = setting_get($pdo, 'maintenance_starts_at', '');
    $message = setting_get($pdo, 'maintenance_message', 'Die ODV-Datenbank ist wegen Wartungsarbeiten gesperrt.');
    $startsTs = $startsAt ? strtotime($startsAt) : false;
    $active = $enabled && (!$startsTs || $startsTs <= time());
    $scheduled = $enabled && $startsTs && $startsTs > time();
    $minutesLeft = $scheduled ? max(0, (int)ceil(($startsTs - time()) / 60)) : 0;
    return [
        'enabled' => $enabled,
        'active' => $active,
        'scheduled' => $scheduled,
        'starts_at' => $startsAt ?: null,
        'minutes_left' => $minutesLeft,
        'message' => $message,
    ];
}

function enforce_maintenance_for_user(PDO $pdo, array $user): void
{
    $state = maintenance_state($pdo);
    if ($state['active'] && !is_superadmin($user)) {
        json_response(['success' => false, 'error' => $state['message'], 'maintenance' => $state], 503);
    }
}

function backup_base_dir(): string
{
    $candidate = dirname(__DIR__) . '/odv_backup/backups';
    if (@is_dir(dirname($candidate)) || @mkdir(dirname($candidate), 0750, true)) {
        return $candidate;
    }
    return __DIR__ . '/backups';
}

function human_size(int $bytes): string
{
    $units = ['B','KB','MB','GB'];
    $size = (float)$bytes;
    $i = 0;
    while ($size >= 1024 && $i < count($units)-1) { $size /= 1024; $i++; }
    return sprintf($i === 0 ? '%.0f %s' : '%.1f %s', $size, $units[$i]);
}

function sql_literal(PDO $pdo, $value): string
{
    if ($value === null) { return 'NULL'; }
    if (is_int($value) || is_float($value)) { return (string)$value; }
    return $pdo->quote((string)$value);
}

function create_pdo_database_backup(PDO $pdo, array $currentUser): array
{
    $dir = backup_base_dir();
    if (!is_dir($dir) && !mkdir($dir, 0750, true) && !is_dir($dir)) {
        json_response(['success' => false, 'error' => 'Backup-Verzeichnis konnte nicht erstellt werden'], 500);
    }
    $date = date('Y-m-d_H-i-s');
    $file = "odv_db_backup_{$date}.sql.gz";
    $path = rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . $file;
    $gz = gzopen($path, 'wb9');
    if (!$gz) {
        json_response(['success' => false, 'error' => 'Backup-Datei konnte nicht geschrieben werden'], 500);
    }
    gzwrite($gz, "-- ODV Datenbanksicherung\n-- Erstellt: " . date('c') . "\n-- Erstellt von: " . ($currentUser['display_name'] ?? '') . "\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n");
    $tables = [];
    foreach ($pdo->query('SHOW TABLES') as $row) {
        $tables[] = array_values($row)[0];
    }
    foreach ($tables as $table) {
        $safe = str_replace('`', '``', (string)$table);
        $create = $pdo->query("SHOW CREATE TABLE `{$safe}`")->fetch(PDO::FETCH_ASSOC);
        $createSql = $create['Create Table'] ?? array_values($create)[1] ?? '';
        gzwrite($gz, "\n-- Tabelle {$table}\nDROP TABLE IF EXISTS `{$safe}`;\n{$createSql};\n\n");
        $stmt = $pdo->query("SELECT * FROM `{$safe}`");
        while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $cols = array_map(fn($c) => '`' . str_replace('`', '``', (string)$c) . '`', array_keys($row));
            $vals = array_map(fn($v) => sql_literal($pdo, $v), array_values($row));
            gzwrite($gz, "INSERT INTO `{$safe}` (" . implode(',', $cols) . ") VALUES (" . implode(',', $vals) . ");\n");
        }
    }
    gzwrite($gz, "\nSET FOREIGN_KEY_CHECKS=1;\n");
    gzclose($gz);
    @chmod($path, 0600);
    $size = filesize($path) ?: 0;
    setting_set($pdo, 'last_backup_file', $file);
    setting_set($pdo, 'last_backup_path', $path);
    setting_set($pdo, 'last_backup_at', date('Y-m-d H:i:s'));
    setting_set($pdo, 'last_backup_size', (string)$size);
    api_log('warning', 'Datenbanksicherung erstellt', ['by_user_id' => $currentUser['id'] ?? null, 'file' => $file, 'size' => $size]);
    return ['file' => $file, 'path' => $path, 'created_at' => date('Y-m-d H:i:s'), 'size' => $size, 'size_human' => human_size((int)$size)];
}

function latest_backup_info(PDO $pdo): array
{
    $file = setting_get($pdo, 'last_backup_file', '');
    $created = setting_get($pdo, 'last_backup_at', '');
    $size = (int)(setting_get($pdo, 'last_backup_size', '0') ?? '0');
    if (!$file) {
        $dir = backup_base_dir();
        $files = glob(rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'odv_db_backup_*.sql.gz') ?: [];
        rsort($files);
        if ($files) {
            $path = $files[0];
            $file = basename($path);
            $created = date('Y-m-d H:i:s', filemtime($path));
            $size = filesize($path) ?: 0;
        }
    }
    if (!$file) { return []; }
    return ['file' => $file, 'created_at' => $created, 'size' => $size, 'size_human' => human_size($size)];
}

function list_database_backups(): array
{
    $dir = backup_base_dir();
    $files = glob(rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'odv_db_backup_*.sql.gz') ?: [];
    rsort($files);
    $items = [];
    foreach ($files as $path) {
        $items[] = [
            'file' => basename($path),
            'created_at' => date('Y-m-d H:i:s', filemtime($path)),
            'size' => filesize($path) ?: 0,
            'size_human' => human_size((int)(filesize($path) ?: 0)),
        ];
    }
    return $items;
}

function database_backup_path_by_file(string $file): string
{
    $file = basename($file);
    if (!preg_match('/^odv_db_backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.sql\.gz$/', $file)) {
        throw new RuntimeException('Ungültiger Backup-Dateiname');
    }
    $path = rtrim(backup_base_dir(), '/\\') . DIRECTORY_SEPARATOR . $file;
    if (!is_file($path)) {
        throw new RuntimeException('Backup-Datei nicht gefunden');
    }
    return $path;
}

function restore_database_backup(PDO $pdo, string $file): array
{
    $path = database_backup_path_by_file($file);
    $gz = gzopen($path, 'rb');
    if (!$gz) {
        throw new RuntimeException('Backup-Datei konnte nicht gelesen werden');
    }
    $statement = '';
    $executed = 0;
    try {
        while (!gzeof($gz)) {
            $line = gzgets($gz);
            if ($line === false) {
                break;
            }
            $trimmed = trim($line);
            if ($trimmed === '' || str_starts_with($trimmed, '--')) {
                continue;
            }
            $statement .= $line;
            if (str_ends_with(rtrim($line), ';')) {
                $sql = trim($statement);
                $statement = '';
                if ($sql !== '') {
                    $pdo->exec($sql);
                    $executed++;
                }
            }
        }
        $rest = trim($statement);
        if ($rest !== '') {
            $pdo->exec($rest);
            $executed++;
        }
    } finally {
        gzclose($gz);
    }
    return [
        'file' => basename($path),
        'statements_executed' => $executed,
        'restored_at' => date('Y-m-d H:i:s'),
    ];
}

function quote_identifier(string $name): string
{
    return '`' . str_replace('`', '``', $name) . '`';
}

function backup_table_for_version(PDO $pdo, string $tableName, string $fromVersion): ?string
{
    if (!db_table_exists($pdo, $tableName)) {
        return null;
    }
    $suffix = preg_replace('/[^A-Za-z0-9_]/', '', $fromVersion);
    $backupName = $tableName . '_' . $suffix;
    if (db_table_exists($pdo, $backupName)) {
        return $backupName;
    }
    $source = quote_identifier($tableName);
    $target = quote_identifier($backupName);
    $pdo->exec("CREATE TABLE {$target} LIKE {$source}");
    $pdo->exec("INSERT INTO {$target} SELECT * FROM {$source}");
    return $backupName;
}

function ensure_schema_migrations_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS odv_schema_migrations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        migration_key VARCHAR(100) NOT NULL,
        from_version VARCHAR(20) NOT NULL,
        to_version VARCHAR(20) NOT NULL,
        description TEXT DEFAULT NULL,
        backup_tables TEXT DEFAULT NULL,
        executed_by_user_id INT DEFAULT NULL,
        executed_by_name VARCHAR(255) DEFAULT NULL,
        executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_migration_key (migration_key),
        INDEX idx_schema_migrations_executed_at (executed_at)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function schema_migration_done(PDO $pdo, string $key): bool
{
    if (!db_table_exists($pdo, 'odv_schema_migrations')) {
        return false;
    }
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM odv_schema_migrations WHERE migration_key = :k");
    $stmt->execute([':k' => $key]);
    return ((int)$stmt->fetchColumn()) > 0;
}

function record_schema_migration(PDO $pdo, string $key, string $fromVersion, string $toVersion, string $description, array $backupTables, array $currentUser): void
{
    ensure_schema_migrations_table($pdo);
    $stmt = $pdo->prepare("INSERT IGNORE INTO odv_schema_migrations
        (migration_key, from_version, to_version, description, backup_tables, executed_by_user_id, executed_by_name)
        VALUES (:migration_key, :from_version, :to_version, :description, :backup_tables, :executed_by_user_id, :executed_by_name)");
    $stmt->execute([
        ':migration_key' => $key,
        ':from_version' => $fromVersion,
        ':to_version' => $toVersion,
        ':description' => $description,
        ':backup_tables' => implode(',', $backupTables),
        ':executed_by_user_id' => (int)($currentUser['id'] ?? 0),
        ':executed_by_name' => (string)($currentUser['display_name'] ?? ''),
    ]);
}

function available_schema_migrations(PDO $pdo): array
{
    return [
        [
            'key' => 'v106_schema_migration_framework',
            'from_version' => 'v105',
            'to_version' => 'v106',
            'description' => 'Migrationsprotokoll fuer kuenftige serverseitige Datenbankanpassungen anlegen.',
            'pending' => !schema_migration_done($pdo, 'v106_schema_migration_framework'),
            'backup_tables' => [],
        ],
        [
            'key' => 'v111_point_rules_optimization',
            'from_version' => 'v110',
            'to_version' => 'v111',
            'description' => 'Punkteregeln auf Metadatenfeld/Wertung, Mindestpruefung, Sonderregeln und manuelle Zusatzpunkte umstellen.',
            'pending' => !schema_migration_done($pdo, 'v111_point_rules_optimization'),
            'backup_tables' => ['point_rules_v110'],
        ],
    ];
}

function apply_schema_migrations(PDO $pdo, array $currentUser): array
{
    $applied = [];
    ensure_schema_migrations_table($pdo);
    if (!schema_migration_done($pdo, 'v106_schema_migration_framework')) {
        record_schema_migration(
            $pdo,
            'v106_schema_migration_framework',
            'v105',
            'v106',
            'Migrationsprotokoll fuer kuenftige serverseitige Datenbankanpassungen angelegt.',
            [],
            $currentUser
        );
        $applied[] = 'v106_schema_migration_framework';
    }
    if (!schema_migration_done($pdo, 'v111_point_rules_optimization')) {
        $backupTables = [];
        $backup = backup_table_for_version($pdo, 'point_rules', 'v110');
        if ($backup) { $backupTables[] = $backup; }
        ensure_point_rules_model_columns($pdo);
        $year = current_points_year();
        $stmt = $pdo->prepare("INSERT INTO point_rules (year, rule_key, label, category, rule_type, source_field, evaluation_source, check_type, min_value, points, is_active, is_system, updated_by_user_id)
            VALUES (:year, :rule_key, :label, :category, :rule_type, :source_field, :evaluation_source, :check_type, :min_value, :points, 1, :is_system, :updated_by_user_id)
            ON DUPLICATE KEY UPDATE label = VALUES(label), category = VALUES(category), rule_type = VALUES(rule_type), source_field = VALUES(source_field), evaluation_source = VALUES(evaluation_source), check_type = VALUES(check_type), min_value = VALUES(min_value), points = VALUES(points), is_active = 1, is_system = VALUES(is_system), updated_by_user_id = VALUES(updated_by_user_id)");
        $keptKeys = [];
        foreach (valid_point_rules_catalog() as $rule) {
            $keptKeys[] = $rule['rule_key'];
            $stmt->execute([
                ':year' => $year,
                ':rule_key' => $rule['rule_key'],
                ':label' => $rule['label'],
                ':category' => $rule['category'],
                ':rule_type' => $rule['rule_type'],
                ':source_field' => $rule['source_field'],
                ':evaluation_source' => $rule['evaluation_source'],
                ':check_type' => $rule['check_type'],
                ':min_value' => (int)($rule['min_value'] ?? 0),
                ':points' => (int)($rule['points'] ?? 0),
                ':is_system' => (int)($rule['is_system'] ?? 0),
                ':updated_by_user_id' => (int)($currentUser['id'] ?? 0),
            ]);
        }
        if ($keptKeys) {
            $placeholders = implode(',', array_fill(0, count($keptKeys), '?'));
            $deleteStmt = $pdo->prepare("DELETE FROM point_rules WHERE year = ? AND rule_key NOT IN ($placeholders)");
            $deleteStmt->execute(array_merge([$year], $keptKeys));
        }
        record_schema_migration(
            $pdo,
            'v111_point_rules_optimization',
            'v110',
            'v111',
            'Punkteregeln auf Metadatenfeld/Wertung, Mindestpruefung, Sonderregeln und manuelle Zusatzpunkte umgestellt.',
            $backupTables,
            $currentUser
        );
        $applied[] = 'v111_point_rules_optimization';
    }
    return $applied;
}


function app_update_state(PDO $pdo): array
{
    $version = setting_get($pdo, 'app_update_version', '');
    $fileName = setting_get($pdo, 'app_update_file_name', '');
    $path = setting_get($pdo, 'app_update_nextcloud_relative_path', '');
    $sha256 = setting_get($pdo, 'app_update_sha256', '');
    $required = setting_get($pdo, 'app_update_required', '0') === '1';
    $notes = setting_get($pdo, 'app_update_release_notes', '');
    $publishedAt = setting_get($pdo, 'app_update_published_at', '');
    return [
        'version' => $version,
        'file_name' => $fileName,
        'file' => $fileName,
        'nextcloud_relative_path' => $path,
        'path' => $path,
        'sha256' => $sha256,
        'required' => $required,
        'release_notes' => $notes,
        'published_at' => $publishedAt ?: null,
        'current_api_version' => ODV_API_VERSION,
        'default_update_folder' => '02_AUSTAUSCH/ODV_UPDATE/Windows',
    ];
}

