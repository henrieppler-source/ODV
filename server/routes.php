<?php
declare(strict_types=1);

require_once __DIR__ . '/database.php';

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$method = $_SERVER['REQUEST_METHOD'];
$path = rtrim($path, '/');

const ODV_API_VERSION = 'v119';

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
    $stmt = $pdo->query("\n        SELECT id, username, display_name, email, role, place, is_active, last_login_at, created_at, updated_at\n        FROM users\n        ORDER BY display_name ASC, username ASC\n    ");
    json_response(['success' => true, 'users' => $stmt->fetchAll()]);
}

if ($method === 'POST' && $path === '/api/users') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $username = trim((string)($input['username'] ?? ''));
    $password = (string)($input['password'] ?? '');
    $displayName = trim((string)($input['display_name'] ?? ''));
    $email = trim((string)($input['email'] ?? ''));
    $role = normalize_role((string)($input['role'] ?? 'ortschronist'));
    $place = trim((string)($input['place'] ?? ''));
    $isActive = isset($input['is_active']) ? (int)(bool)$input['is_active'] : 1;

    if ($username === '' || $password === '' || $displayName === '') {
        json_response(['success' => false, 'error' => 'Benutzername, Passwort und Name sind erforderlich'], 400);
    }

    $passwordHash = password_hash($password, PASSWORD_DEFAULT);
    $pdo = db();

    try {
        $stmt = $pdo->prepare("\n            INSERT INTO users (username, password_hash, display_name, role, place, is_active)\n            VALUES (:username, :password_hash, :display_name, :role, :place, :is_active)\n        ");
        $stmt->execute([
            ':username' => $username,
            ':password_hash' => $passwordHash,
            ':display_name' => $displayName,
            ':email' => $email !== '' ? $email : null,
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
    try {
        if ($password !== '') {
            $passwordHash = password_hash($password, PASSWORD_DEFAULT);
            $stmt = $pdo->prepare("\n                UPDATE users\n                SET username = :username, password_hash = :password_hash, display_name = :display_name, email = :email, role = :role, place = :place, is_active = :is_active\n                WHERE id = :id\n            ");
            $stmt->execute([
                ':id' => $userId,
                ':username' => $username,
                ':password_hash' => $passwordHash,
                ':display_name' => $displayName,
                ':email' => $email !== '' ? $email : null,
                ':role' => $role,
                ':place' => $place !== '' ? $place : null,
                ':is_active' => $isActive,
            ]);
        } else {
            $stmt = $pdo->prepare("\n                UPDATE users\n                SET username = :username, display_name = :display_name, email = :email, role = :role, place = :place, is_active = :is_active\n                WHERE id = :id\n            ");
            $stmt->execute([
                ':id' => $userId,
                ':username' => $username,
                ':display_name' => $displayName,
                ':email' => $email !== '' ? $email : null,
                ':role' => $role,
                ':place' => $place !== '' ? $place : null,
                ':is_active' => $isActive,
            ]);
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

if ($method === 'POST' && $path === '/api/documents') {
    $currentUser = current_user();
    $input = get_json_input();

    $uploadId = trim((string)($input['upload_id'] ?? ''));
    $originalFilename = trim((string)($input['original_filename'] ?? ''));
    $storedFilename = trim((string)($input['stored_filename'] ?? $originalFilename));
    $currentFilename = trim((string)($input['current_filename'] ?? $storedFilename));
    $targetFolder = trim((string)($input['target_folder'] ?? ''));
    $currentPath = trim((string)($input['current_path'] ?? ''));
    $uploadedAt = trim((string)($input['uploaded_at'] ?? date('Y-m-d H:i:s')));
    $status = validate_document_status(trim((string)($input['status'] ?? 'hochgeladen')));
    $metadata = is_array($input['metadata'] ?? null) ? $input['metadata'] : [];
    $captureMode = trim((string)($input['odv_capture_mode'] ?? 'odv_upload'));

    if ($uploadId === '' || $originalFilename === '') {
        json_response(['success' => false, 'error' => 'upload_id und original_filename sind erforderlich'], 400);
    }

    $pdo = db();
    $uploadOwner = $currentUser;
    $requestedOwnerId = (int)($input['import_uploaded_by_user_id'] ?? $input['uploaded_by_user_id'] ?? 0);
    if ($requestedOwnerId > 0) {
        if ($requestedOwnerId !== (int)($currentUser['id'] ?? 0) && !is_admin_role($currentUser)) {
            json_response(['success' => false, 'error' => 'Nur Admins dürfen beim Erfassen einen anderen Benutzer zuordnen'], 403);
        }
        $ownerStmt = $pdo->prepare("SELECT id, username, display_name, email, role, place, is_active FROM users WHERE id = :id LIMIT 1");
        $ownerStmt->execute([':id' => $requestedOwnerId]);
        $owner = $ownerStmt->fetch();
        if (!$owner || (int)($owner['is_active'] ?? 0) !== 1) {
            json_response(['success' => false, 'error' => 'Gewählter Benutzer für Import nicht gefunden oder deaktiviert'], 400);
        }
        $uploadOwner = [
            'id' => (int)$owner['id'],
            'username' => $owner['username'],
            'display_name' => $owner['display_name'],
            'email' => $owner['email'] ?? null,
            'role' => $owner['role'],
            'place' => $owner['place'],
        ];
    }

    $permissionDoc = [
        'target_folder' => $targetFolder,
        'current_path' => $currentPath,
        'uploaded_by_user_id' => $currentUser['id'],
    ];
    ensure_document_write_permission($pdo, $currentUser, $permissionDoc);

    try {
        $pdo->beginTransaction();
        $stmt = $pdo->prepare("\n            INSERT INTO documents (\n                upload_id, original_filename, stored_filename, current_filename, target_folder, current_path,\n                uploaded_by_user_id, uploaded_by_name, uploaded_at, status, points_eligible,\n                document_type, source, original_location, document_date, event, place, description, note,\n                copyright_author, rights_holder, usage_permission, license_note, rights_note,\n                archive_name, archive_signature, archive_accessed_at, keywords, transcription_done, transcription_type, transcription_note, person_status, json_metadata\n            ) VALUES (\n                :upload_id, :original_filename, :stored_filename, :current_filename, :target_folder, :current_path,\n                :uploaded_by_user_id, :uploaded_by_name, :uploaded_at, :status, :points_eligible,\n                :document_type, :source, :original_location, :document_date, :event, :place, :description, :note,\n                :copyright_author, :rights_holder, :usage_permission, :license_note, :rights_note,\n                :archive_name, :archive_signature, :archive_accessed_at, :keywords, :transcription_done, :transcription_type, :transcription_note, :person_status, :json_metadata\n            )\n        ");
        $stmt->execute([
            ':upload_id' => $uploadId,
            ':original_filename' => $originalFilename,
            ':stored_filename' => $storedFilename,
            ':current_filename' => $currentFilename,
            ':target_folder' => $targetFolder !== '' ? $targetFolder : null,
            ':current_path' => $currentPath !== '' ? $currentPath : null,
            ':points_eligible' => (is_point_eligible_path($targetFolder) || is_point_eligible_path($currentPath)) ? 1 : 0,
            ':uploaded_by_user_id' => $uploadOwner['id'],
            ':uploaded_by_name' => $uploadOwner['display_name'],
            ':uploaded_at' => $uploadedAt,
            ':status' => $status,
            ':document_type' => (string)($metadata['document_type'] ?? ''),
            ':source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? ''),
            ':original_location' => (string)($metadata['standort_original'] ?? $metadata['original_location'] ?? ''),
            ':document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? ''),
            ':event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? ''),
            ':place' => (string)($metadata['ort'] ?? $metadata['place'] ?? $uploadOwner['place'] ?? ''),
            ':description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? ''),
            ':note' => (string)($metadata['bemerkung'] ?? $metadata['note'] ?? ''),
            ':copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? ''),
            ':rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? ''),
            ':usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? ''),
            ':license_note' => (string)($metadata['lizenz'] ?? $metadata['license_note'] ?? ''),
            ':rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? ''),
            ':archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? ''),
            ':archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? ''),
            ':archive_accessed_at' => (string)($metadata['abruf_am'] ?? $metadata['archive_accessed_at'] ?? ''),
            ':keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? ''),
            ':transcription_done' => !empty($metadata['transcription_done']) ? 1 : 0,
            ':transcription_type' => (string)($metadata['transcription_type'] ?? ''),
            ':transcription_note' => (string)($metadata['transcription_note'] ?? ''),
            ':person_status' => (string)($input['person_status'] ?? 'none'),
            ':json_metadata' => json_encode($input, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
        ]);

        $documentId = (int)$pdo->lastInsertId();
        $history = $pdo->prepare("\n            INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details)\n            VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details)\n        ");
        $history->execute([
            ':document_id' => $documentId,
            ':upload_id' => $uploadId,
            ':user_id' => $currentUser['id'],
            ':user_display_name' => $currentUser['display_name'],
            ':action' => ($captureMode === 'existing_file_metadata' ? 'existing_file_captured' : 'document_created'),
            ':details' => ($captureMode === 'existing_file_metadata' ? 'Vorhandene Nextcloud-Datei in ODV aufgenommen' : 'Dokument wurde über API angelegt')
        ]);
        add_auto_points_for_metadata($pdo, $documentId, $uploadId, $uploadOwner, [
            'description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? ''),
            'keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? ''),
            'source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? ''),
            'usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? ''),
            'rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? ''),
            'copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? ''),
            'rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? ''),
            'archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? ''),
            'archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? ''),
            'document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? ''),
            'event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? ''),
            'transcription_done' => !empty($metadata['transcription_done']),
            'transcription_type' => (string)($metadata['transcription_type'] ?? ''),
        ], null, is_array($metadata['openai_metadata_fields'] ?? null) ? $metadata['openai_metadata_fields'] : []);
        add_special_collection_points($pdo, $documentId, $uploadId, $currentUser, $targetFolder, $currentPath, $captureMode);
        $pdo->commit();
        api_log('info', 'Dokument angelegt', ['user_id' => $currentUser['id'], 'upload_id' => $uploadId]);
        json_response(['success' => true, 'message' => 'Dokument wurde gespeichert', 'document_id' => $documentId, 'upload_id' => $uploadId], 201);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        if ((int)$e->getCode() === 23000) {
            json_response(['success' => false, 'error' => 'upload_id ist bereits vorhanden'], 409);
        }
        api_log('error', 'Dokument konnte nicht gespeichert werden', ['pdo_code' => $e->getCode(), 'upload_id' => $uploadId, 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokument konnte nicht gespeichert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/documents') {
    $currentUser = current_user();
    $pdo = db();
    try {
        $status = trim((string)($_GET['status'] ?? ''));
        $onlyOwn = (int)($_GET['only_own'] ?? 0);
        $where = [];
        $params = [];
        if ($status !== '') {
            $where[] = "status = :status";
            $params[':status'] = $status;
        } else {
            // Archivierte Dokumente bleiben erhalten, erscheinen aber nicht in Standardlisten.
            $where[] = "status <> 'archiviert'";
        }
        if ($onlyOwn === 1 && role_key($currentUser) === 'ortschronist') {
            $where[] = "uploaded_by_user_id = :user_id";
            $params[':user_id'] = $currentUser['id'];
        }
        $whereSql = count($where) > 0 ? 'WHERE ' . implode(' AND ', $where) : '';
        $stmt = $pdo->prepare("
            SELECT id, upload_id, original_filename, stored_filename, current_filename, target_folder, current_path,
                   uploaded_by_user_id, uploaded_by_name, uploaded_at, status, document_type, source, original_location, document_date,
                   event, place, description, note, copyright_author, rights_holder, usage_permission, license_note,
                   rights_note, archive_name, archive_signature, archive_accessed_at, keywords, transcription_done, transcription_type, transcription_note, person_status, json_metadata, created_at, updated_at
            FROM documents
            {$whereSql}
            ORDER BY uploaded_at DESC, id DESC
            LIMIT 500
        ");
        $stmt->execute($params);
        $documents = $stmt->fetchAll();
        if (!is_superadmin($currentUser)) {
            $filtered = [];
            foreach ($documents as $doc) {
                $pathForPermission = (string)(($doc['target_folder'] ?? '') !== '' ? $doc['target_folder'] : ($doc['current_path'] ?? ''));
                if ($pathForPermission === '' || user_has_folder_permission($pdo, $currentUser, $pathForPermission, 'read')) {
                    $filtered[] = $doc;
                }
            }
            $documents = $filtered;
        }
        json_response(['success' => true, 'documents' => $documents]);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentliste konnte nicht geladen werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokumentliste konnte nicht geladen werden'], 500);
    }
}



if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/access-log$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $rawAction = trim((string)($input['action'] ?? 'opened'));
    $action = $rawAction === 'downloaded' ? 'document_downloaded' : 'document_opened';
    $localPath = trim((string)($input['local_path'] ?? ''));
    $pdo = db();
    try {
        $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
        $stmt->execute([':upload_id' => $uploadId]);
        $document = $stmt->fetch();
        if (!$document) {
            json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
        }
        ensure_document_read_permission($pdo, $currentUser, $document);
        $details = $action === 'document_downloaded' ? 'Dokument über ODV heruntergeladen/kopiert' : 'Dokument über ODV geöffnet';
        if ($localPath !== '') {
            $details .= ': ' . basename($localPath);
        }
        $hist = $pdo->prepare("INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, new_value) VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :new_value)");
        $hist->execute([
            ':document_id' => (int)$document['id'],
            ':upload_id' => $uploadId,
            ':user_id' => (int)$currentUser['id'],
            ':user_display_name' => (string)$currentUser['display_name'],
            ':action' => $action,
            ':details' => $details,
            ':new_value' => $localPath,
        ]);
        json_response(['success' => true, 'message' => 'Dokumentzugriff protokolliert']);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentzugriff konnte nicht protokolliert werden', ['error' => $e->getMessage(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Dokumentzugriff konnte nicht protokolliert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/document-access-log') {
    $currentUser = require_role(['Admin', 'Superadmin']);
    $pdo = db();
    $limit = max(1, min(1000, (int)($_GET['limit'] ?? 500)));
    try {
        $stmt = $pdo->prepare("\n            SELECT h.id, h.upload_id, h.user_id, h.user_display_name, h.action, h.details, h.new_value, h.created_at,\n                   d.current_filename, d.original_filename, d.current_path, d.target_folder\n            FROM document_history h\n            LEFT JOIN documents d ON d.upload_id = h.upload_id\n            WHERE h.action IN ('document_opened', 'document_downloaded')\n            ORDER BY h.created_at DESC, h.id DESC\n            LIMIT {$limit}\n        ");
        $stmt->execute();
        json_response(['success' => true, 'entries' => $stmt->fetchAll()]);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentzugriffsliste konnte nicht geladen werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokumentzugriffsliste konnte nicht geladen werden'], 500);
    }
}


if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/lock$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) { json_response(['success'=>false, 'error'=>'Dokument nicht gefunden'], 404); }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$document['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) { json_response(['success'=>false, 'error'=>'Keine Bearbeitungsberechtigung für dieses Dokument'], 403); }
    acquire_document_lock($pdo, $currentUser, $uploadId);
    json_response(['success'=>true, 'message'=>'Dokument wurde zur Bearbeitung gesperrt']);
}

if ($method === 'DELETE' && preg_match('#^/api/documents/([^/]+)/lock$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    ensure_security_tables($pdo);
    $stmt = $pdo->prepare("DELETE FROM odv_document_locks WHERE upload_id=:upload_id AND (locked_by_user_id=:uid OR :is_admin=1)");
    $stmt->execute([':upload_id'=>$uploadId, ':uid'=>(int)$currentUser['id'], ':is_admin'=>is_superadmin($currentUser) ? 1 : 0]);
    json_response(['success'=>true, 'message'=>'Dokumentsperre gelöst']);
}

if ($method === 'GET' && preg_match('#^/api/documents/([^/]+)$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    ensure_document_read_permission($pdo, $currentUser, $document);
    $historyStmt = $pdo->prepare("\n        SELECT id, user_display_name, action, details, old_value, new_value, created_at\n        FROM document_history\n        WHERE upload_id = :upload_id\n        ORDER BY created_at ASC, id ASC\n    ");
    $historyStmt->execute([':upload_id' => $uploadId]);
    $personsStmt = $pdo->prepare("\n        SELECT id, number, display_name, x, y, certainty, note, created_by_name, created_at, updated_at\n        FROM document_persons\n        WHERE document_id = :document_id\n        ORDER BY number ASC\n    ");
    $personsStmt->execute([':document_id' => $document['id']]);
    json_response([
        'success' => true,
        'document' => $document,
        'persons' => $personsStmt->fetchAll(),
        'history' => $historyStmt->fetchAll()
    ]);
}

if ($method === 'PUT' && preg_match('#^/api/documents/([^/]+)$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $existing = $stmt->fetch();
    if (!$existing) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$existing['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) {
        json_response(['success' => false, 'error' => 'Keine Berechtigung für dieses Dokument'], 403);
    }
    acquire_document_lock($pdo, $currentUser, $uploadId);
    $metadata = is_array($input['metadata'] ?? null) ? $input['metadata'] : [];
    $captureMode = trim((string)($input['odv_capture_mode'] ?? 'odv_upload'));
    $newValues = [
        'current_filename' => trim((string)($input['current_filename'] ?? $existing['current_filename'])),
        'target_folder' => trim((string)($input['target_folder'] ?? $existing['target_folder'])),
        'current_path' => trim((string)($input['current_path'] ?? $existing['current_path'])),
        'status' => validate_document_status(trim((string)($input['status'] ?? $existing['status']))),
        'document_type' => (string)($metadata['document_type'] ?? $input['document_type'] ?? $existing['document_type']),
        'source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? $input['source'] ?? $existing['source']),
        'original_location' => (string)($metadata['standort_original'] ?? $metadata['original_location'] ?? $input['original_location'] ?? $existing['original_location']),
        'document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? $input['document_date'] ?? $existing['document_date']),
        'event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? $input['event'] ?? $existing['event']),
        'place' => (string)($metadata['ort'] ?? $metadata['place'] ?? $input['place'] ?? $existing['place']),
        'description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? $input['description'] ?? $existing['description']),
        'note' => (string)($metadata['bemerkung'] ?? $metadata['note'] ?? $input['note'] ?? $existing['note']),
        'copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? $input['copyright_author'] ?? $existing['copyright_author']),
        'rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? $input['rights_holder'] ?? $existing['rights_holder']),
        'usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? $input['usage_permission'] ?? $existing['usage_permission']),
        'license_note' => (string)($metadata['lizenz'] ?? $metadata['license_note'] ?? $input['license_note'] ?? $existing['license_note']),
        'rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? $input['rights_note'] ?? $existing['rights_note']),
        'archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? $input['archive_name'] ?? $existing['archive_name']),
        'archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? $input['archive_signature'] ?? $existing['archive_signature']),
        'archive_accessed_at' => (string)($metadata['abruf_am'] ?? $metadata['archive_accessed_at'] ?? $input['archive_accessed_at'] ?? $existing['archive_accessed_at']),
        'keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? $input['keywords'] ?? $existing['keywords'] ?? ''),
        'transcription_done' => !empty($metadata['transcription_done'] ?? $input['transcription_done'] ?? $existing['transcription_done'] ?? 0) ? 1 : 0,
        'transcription_type' => (string)($metadata['transcription_type'] ?? $input['transcription_type'] ?? $existing['transcription_type'] ?? ''),
        'transcription_note' => (string)($metadata['transcription_note'] ?? $input['transcription_note'] ?? $existing['transcription_note'] ?? ''),
        'person_status' => (string)($input['person_status'] ?? $existing['person_status']),
        'json_metadata' => json_encode($input, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
    ];
    $newUploadedByUserId = (int)($existing['uploaded_by_user_id'] ?? 0);
    $newUploadedByName = (string)($existing['uploaded_by_name'] ?? '');
    if ($isAdmin && isset($input['uploaded_by_user_id']) && (int)$input['uploaded_by_user_id'] > 0) {
        $uStmt = $pdo->prepare("SELECT id, display_name FROM users WHERE id = :id LIMIT 1");
        $uStmt->execute([':id' => (int)$input['uploaded_by_user_id']]);
        $uRow = $uStmt->fetch();
        if ($uRow) {
            $newUploadedByUserId = (int)$uRow['id'];
            $newUploadedByName = (string)$uRow['display_name'];
        }
    }
    if (!$isAdmin) {
        if ((string)$existing['status'] === 'uebernommen') {
            json_response(['success' => false, 'error' => 'Übernommene Dokumente dürfen nur durch Admins geändert werden'], 403);
        }
        if ($newValues['status'] !== $existing['status']) {
            json_response(['success' => false, 'error' => 'Status darf nur durch Admins geändert werden'], 403);
        }
        if ((string)$newValues['target_folder'] !== (string)($existing['target_folder'] ?? '')) {
            json_response(['success' => false, 'error' => 'Zielordner darf nur durch Admins geändert werden'], 403);
        }
        $oldPathNorm = str_replace('\\', '/', (string)($existing['current_path'] ?? ''));
        $newPathNorm = str_replace('\\', '/', (string)($newValues['current_path'] ?? ''));
        $oldDir = dirname($oldPathNorm);
        $newDir = dirname($newPathNorm);
        if ($oldDir !== $newDir) {
            json_response(['success' => false, 'error' => 'Dateien dürfen nur durch Admins verschoben werden'], 403);
        }
    }

    $permissionDoc = $existing;
    $permissionDoc['target_folder'] = $newValues['target_folder'];
    $permissionDoc['current_path'] = $newValues['current_path'];
    ensure_document_write_permission($pdo, $currentUser, $permissionDoc);

    try {
        $pdo->beginTransaction();
        $update = $pdo->prepare("\n            UPDATE documents SET\n                current_filename = :current_filename, target_folder = :target_folder, current_path = :current_path, status = :status,\n                uploaded_by_user_id = :uploaded_by_user_id, uploaded_by_name = :uploaded_by_name,\n                document_type = :document_type, source = :source, original_location = :original_location, document_date = :document_date,\n                event = :event, place = :place, description = :description, note = :note,\n                copyright_author = :copyright_author, rights_holder = :rights_holder, usage_permission = :usage_permission,\n                license_note = :license_note, rights_note = :rights_note, archive_name = :archive_name, archive_signature = :archive_signature,\n                archive_accessed_at = :archive_accessed_at, keywords = :keywords, transcription_done = :transcription_done, transcription_type = :transcription_type, transcription_note = :transcription_note, person_status = :person_status, json_metadata = :json_metadata\n            WHERE upload_id = :upload_id\n        ");
        $update->execute([
            ':upload_id' => $uploadId,
            ':current_filename' => $newValues['current_filename'],
            ':target_folder' => $newValues['target_folder'] !== '' ? $newValues['target_folder'] : null,
            ':current_path' => $newValues['current_path'] !== '' ? $newValues['current_path'] : null,
            ':status' => $newValues['status'],
            ':uploaded_by_user_id' => $newUploadedByUserId,
            ':uploaded_by_name' => $newUploadedByName,
            ':document_type' => $newValues['document_type'],
            ':source' => $newValues['source'],
            ':original_location' => $newValues['original_location'],
            ':document_date' => $newValues['document_date'],
            ':event' => $newValues['event'],
            ':place' => $newValues['place'],
            ':description' => $newValues['description'],
            ':note' => $newValues['note'],
            ':copyright_author' => $newValues['copyright_author'],
            ':rights_holder' => $newValues['rights_holder'],
            ':usage_permission' => $newValues['usage_permission'],
            ':license_note' => $newValues['license_note'],
            ':rights_note' => $newValues['rights_note'],
            ':archive_name' => $newValues['archive_name'],
            ':archive_signature' => $newValues['archive_signature'],
            ':archive_accessed_at' => $newValues['archive_accessed_at'],
            ':keywords' => $newValues['keywords'],
            ':transcription_done' => $newValues['transcription_done'],
            ':transcription_type' => $newValues['transcription_type'],
            ':transcription_note' => $newValues['transcription_note'],
            ':person_status' => $newValues['person_status'],
            ':json_metadata' => $newValues['json_metadata'],
        ]);
        $changes = [];
        foreach ($newValues as $field => $newValue) {
            if ($field === 'json_metadata') {
                continue;
            }
            $oldValue = (string)($existing[$field] ?? '');
            if ((string)$newValue !== $oldValue) {
                $changes[] = ['field' => $field, 'old' => $oldValue, 'new' => (string)$newValue];
            }
        }
        if ($newUploadedByUserId !== (int)($existing['uploaded_by_user_id'] ?? 0)) {
            $changes[] = ['field' => 'uploaded_by', 'old' => (string)($existing['uploaded_by_name'] ?? ''), 'new' => $newUploadedByName];
            // Automatische, dem bisherigen Hochlader gutgeschriebene Punkte werden auf den neuen Hochlader übertragen.
            $transfer = $pdo->prepare("UPDATE contribution_points SET user_id = :new_user_id, user_display_name = :new_name WHERE document_id = :document_id AND user_id = :old_user_id AND is_manual = 0");
            $transfer->execute([':new_user_id' => $newUploadedByUserId, ':new_name' => $newUploadedByName, ':document_id' => (int)$existing['id'], ':old_user_id' => (int)($existing['uploaded_by_user_id'] ?? 0)]);
        }
        if (count($changes) > 0) {
            $history = $pdo->prepare("\n                INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, old_value, new_value)\n                VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :old_value, :new_value)\n            ");
            foreach ($changes as $change) {
                $history->execute([
                    ':document_id' => $existing['id'],
                    ':upload_id' => $uploadId,
                    ':user_id' => $currentUser['id'],
                    ':user_display_name' => $currentUser['display_name'],
                    ':action' => 'document_updated',
                    ':details' => 'Feld geändert: ' . $change['field'],
                    ':old_value' => $change['old'],
                    ':new_value' => $change['new'],
                ]);
            }
        }
        add_auto_points_for_metadata($pdo, (int)$existing['id'], $uploadId, $currentUser, $newValues, $existing, is_array($metadata['openai_metadata_fields'] ?? null) ? $metadata['openai_metadata_fields'] : []);
        if (($newValues['status'] ?? '') === 'uebernommen' && ($existing['status'] ?? '') !== 'uebernommen') {
            add_contribution_point($pdo, (int)$existing['id'], $uploadId, $currentUser, $currentUser, 'admin_review', 'admin_review_accepted', 'Dokument geprüft und übernommen', 'status', point_rule_points($pdo, current_points_year(), 'admin_review_accepted', 1), false);
        }
        if ((string)($newValues['current_path'] ?? '') !== (string)($existing['current_path'] ?? '') || (string)($newValues['current_filename'] ?? '') !== (string)($existing['current_filename'] ?? '')) {
            add_contribution_point($pdo, (int)$existing['id'], $uploadId, $currentUser, $currentUser, 'admin_review', 'admin_file_organization', 'Datei umbenannt oder verschoben', 'current_path', point_rule_points($pdo, current_points_year(), 'admin_file_organization', 1), false);
        }
        $pdo->commit();
        json_response(['success' => true, 'message' => 'Dokument wurde aktualisiert', 'upload_id' => $uploadId, 'changes' => $changes]);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        api_log('error', 'Dokument konnte nicht aktualisiert werden', ['pdo_code' => $e->getCode(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Dokument konnte nicht aktualisiert werden'], 500);
    }
}

if ($method === 'PUT' && preg_match('#^/api/documents/([^/]+)/persons$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $persons = $input['persons'] ?? null;
    if (!is_array($persons)) {
        json_response(['success' => false, 'error' => 'persons muss ein Array sein'], 400);
    }
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$document['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) {
        json_response(['success' => false, 'error' => 'Keine Berechtigung für dieses Dokument'], 403);
    }
    ensure_document_write_permission($pdo, $currentUser, $document);
    try {
        $pdo->beginTransaction();
        $delete = $pdo->prepare("DELETE FROM document_persons WHERE document_id = :document_id");
        $delete->execute([':document_id' => $document['id']]);
        $insert = $pdo->prepare("\n            INSERT INTO document_persons (document_id, number, display_name, x, y, certainty, note, created_by_user_id, created_by_name)\n            VALUES (:document_id, :number, :display_name, :x, :y, :certainty, :note, :created_by_user_id, :created_by_name)\n        ");
        $count = 0;
        foreach ($persons as $person) {
            if (!is_array($person)) {
                continue;
            }
            $number = (int)($person['number'] ?? 0);
            $displayName = trim((string)($person['display_name'] ?? $person['name'] ?? ''));
            $x = $person['x'] ?? null;
            $y = $person['y'] ?? null;
            $certainty = trim((string)($person['certainty'] ?? ''));
            $note = trim((string)($person['note'] ?? ''));
            if ($number <= 0) {
                $number = $count + 1;
            }
            $insert->execute([
                ':document_id' => $document['id'],
                ':number' => $number,
                ':display_name' => $displayName !== '' ? $displayName : null,
                ':x' => $x !== null ? (float)$x : null,
                ':y' => $y !== null ? (float)$y : null,
                ':certainty' => $certainty !== '' ? $certainty : null,
                ':note' => $note !== '' ? $note : null,
                ':created_by_user_id' => $currentUser['id'],
                ':created_by_name' => $currentUser['display_name'],
            ]);
            $count++;
        }
        $personStatus = $count > 0 ? 'identified' : 'none';
        $updateDoc = $pdo->prepare("UPDATE documents SET person_status = :person_status WHERE id = :id");
        $updateDoc->execute([':person_status' => $personStatus, ':id' => $document['id']]);
        $history = $pdo->prepare("\n            INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, old_value, new_value)\n            VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :old_value, :new_value)\n        ");
        $history->execute([
            ':document_id' => $document['id'],
            ':upload_id' => $uploadId,
            ':user_id' => $currentUser['id'],
            ':user_display_name' => $currentUser['display_name'],
            ':action' => 'persons_updated',
            ':details' => 'Personenzuordnung wurde gespeichert',
            ':old_value' => $document['person_status'],
            ':new_value' => $personStatus,
        ]);
        add_person_points($pdo, (int)$document['id'], $uploadId, $currentUser, $persons);
        $pdo->commit();
        json_response(['success' => true, 'message' => 'Personenzuordnung wurde gespeichert', 'upload_id' => $uploadId, 'count' => $count, 'person_status' => $personStatus]);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        api_log('error', 'Personenzuordnung konnte nicht gespeichert werden', ['pdo_code' => $e->getCode(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Personenzuordnung konnte nicht gespeichert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/folder-permissions') {
    $currentUser = current_user();
    $pdo = db();
    json_response([
        'success' => true,
        'user_id' => $currentUser['id'],
        'permissions' => fetch_user_folder_permissions($pdo, (int)$currentUser['id'], (string)$currentUser['role'])
    ]);
}

if ($method === 'GET' && preg_match('#^/api/users/(\d+)/folder-permissions$#', $path, $matches)) {
    require_role(['superadmin']);
    $userId = (int)$matches[1];
    $pdo = db();
    $stmt = $pdo->prepare("SELECT id, role FROM users WHERE id = :id LIMIT 1");
    $stmt->execute([':id' => $userId]);
    $user = $stmt->fetch();
    if (!$user) {
        json_response(['success' => false, 'error' => 'Benutzer nicht gefunden'], 404);
    }
    json_response([
        'success' => true,
        'user_id' => $userId,
        'permissions' => fetch_user_folder_permissions($pdo, $userId, (string)$user['role'])
    ]);
}

if ($method === 'PUT' && preg_match('#^/api/users/(\d+)/folder-permissions$#', $path, $matches)) {
    $currentUser = require_role(['superadmin']);
    $userId = (int)$matches[1];
    $input = get_json_input();
    $rows = $input['permissions'] ?? null;
    if (!is_array($rows)) {
        json_response(['success' => false, 'error' => 'permissions muss ein Array sein'], 400);
    }
    $allowed = array_keys(folder_groups());
    $pdo = db();
    $pdo->beginTransaction();
    try {
        $delete = $pdo->prepare("DELETE FROM user_folder_permissions WHERE user_id = :user_id");
        $delete->execute([':user_id' => $userId]);
        $insert = $pdo->prepare("\n            INSERT INTO user_folder_permissions (user_id, folder_group, can_read, can_write, updated_by_user_id)\n            VALUES (:user_id, :folder_group, :can_read, :can_write, :updated_by_user_id)\n        ");
        foreach ($rows as $row) {
            if (!is_array($row)) { continue; }
            $group = (string)($row['folder_group'] ?? '');
            if (!in_array($group, $allowed, true)) { continue; }
            $insert->execute([
                ':user_id' => $userId,
                ':folder_group' => $group,
                ':can_read' => (int)(bool)($row['can_read'] ?? false),
                ':can_write' => (int)(bool)($row['can_write'] ?? false),
                ':updated_by_user_id' => $currentUser['id'],
            ]);
        }
        $pdo->commit();
        api_log('info', 'Ordnerrechte gespeichert', ['by_user_id' => $currentUser['id'], 'user_id' => $userId]);
        json_response(['success' => true, 'message' => 'Ordnerrechte wurden gespeichert']);
    } catch (PDOException $e) {
        try { $pdo->exec("SET FOREIGN_KEY_CHECKS = 1"); } catch (Throwable $ignore) {}
        if ($pdo->inTransaction()) { $pdo->rollBack(); }
        api_log('error', 'Ordnerrechte konnten nicht gespeichert werden', ['pdo_code' => $e->getCode()]);
        json_response(['success' => false, 'error' => 'Ordnerrechte konnten nicht gespeichert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/place-folders') {
    current_user();
    $pdo = db();
    $stmt = $pdo->query("SELECT id, place, folder_name, is_active FROM place_folders WHERE is_active = 1 ORDER BY place ASC");
    json_response(['success' => true, 'places' => $stmt->fetchAll()]);
}

if ($method === 'PUT' && $path === '/api/place-folders') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $rows = $input['places'] ?? null;
    if (!is_array($rows)) {
        json_response(['success' => false, 'error' => 'places muss ein Array sein'], 400);
    }
    $pdo = db();
    $pdo->beginTransaction();
    try {
        $pdo->exec("DELETE FROM place_folders");
        $insert = $pdo->prepare("\n            INSERT INTO place_folders (place, folder_name, is_active, updated_by_user_id)\n            VALUES (:place, :folder_name, 1, :updated_by_user_id)\n        ");
        foreach ($rows as $row) {
            if (!is_array($row)) { continue; }
            $place = trim((string)($row['place'] ?? ''));
            $folder = trim((string)($row['folder_name'] ?? ''));
            if ($place === '' || $folder === '') { continue; }
            $insert->execute([
                ':place' => $place,
                ':folder_name' => $folder,
                ':updated_by_user_id' => $currentUser['id'],
            ]);
        }
        $pdo->commit();
        api_log('info', 'Ortsordner-Stammdaten gespeichert', ['by_user_id' => $currentUser['id']]);
        json_response(['success' => true, 'message' => 'Ortsordner-Stammdaten wurden gespeichert']);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) { $pdo->rollBack(); }
        api_log('error', 'Ortsordner-Stammdaten konnten nicht gespeichert werden', ['pdo_code' => $e->getCode()]);
        json_response(['success' => false, 'error' => 'Ortsordner-Stammdaten konnten nicht gespeichert werden'], 500);
    }
}



function ensure_mail_group_external_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS mail_group_external_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL,
        first_name VARCHAR(255) DEFAULT NULL,
        last_name VARCHAR(255) DEFAULT NULL,
        email VARCHAR(255) NOT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_mgem_group (group_id),
        INDEX idx_mgem_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

function valid_point_rules_catalog(): array
{
    $rules = [];
    foreach (metadata_point_rule_catalog() as $field => $info) {
        foreach ([['manual', 2], ['openAI', 1]] as [$source, $points]) {
            $rules[] = [
                'rule_key' => metadata_point_rule_key($field, $source),
                'label' => $info['label'],
                'category' => 'metadata',
                'rule_type' => 'metadata',
                'source_field' => $field,
                'evaluation_source' => $source,
                'check_type' => $info['check_type'],
                'min_value' => $info['min_value'],
                'meaning' => ($source === 'openAI' ? 'Durch OpenAI befülltes Metadatenfeld' : 'Manuell befülltes Metadatenfeld'),
                'points' => $points,
                'source' => $source,
                'is_system' => 0,
            ];
        }
    }
    return array_merge($rules, [
        ['rule_key'=>'transcription_short','label'=>'Kurze Transkription / Auszug','category'=>'metadata','rule_type'=>'system','source_field'=>'transcription_done','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Transkription ja + Art kurz','points'=>3,'source'=>'System','is_system'=>1],
        ['rule_key'=>'transcription_full','label'=>'Vollständige Transkription','category'=>'metadata','rule_type'=>'system','source_field'=>'transcription_done','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Transkription ja + Art vollständig','points'=>5,'source'=>'System','is_system'=>1],
        ['rule_key'=>'transcription_difficult','label'=>'Schwierige Handschrift / alte Schrift','category'=>'metadata','rule_type'=>'system','source_field'=>'transcription_done','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Transkriptionsart schwierige Handschrift','points'=>8,'source'=>'System','is_system'=>1],
        ['rule_key'=>'transcription_document','label'=>'Transkription Zeitung / Akte / Urkunde','category'=>'metadata','rule_type'=>'system','source_field'=>'transcription_done','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Transkription einer Zeitung, Akte oder Urkunde','points'=>10,'source'=>'System','is_system'=>1],
        ['rule_key'=>'persons_image_marked','label'=>'Bild mit Personenmarkierungen','category'=>'persons','rule_type'=>'system','source_field'=>'persons_image','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Bild hochgeladen und mindestens eine Person markiert','points'=>5,'source'=>'System','is_system'=>1],
        ['rule_key'=>'persons_per_person','label'=>'Personenmarkierung je Person','category'=>'persons','rule_type'=>'system','source_field'=>'persons','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Zusätzlich je markierter Person auf einem Bild','points'=>1,'source'=>'System','is_system'=>1],
        ['rule_key'=>'admin_review_accepted','label'=>'Dokument geprüft und übernommen','category'=>'admin_review','rule_type'=>'system','source_field'=>'status','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Admin übernimmt Dokument fachlich','points'=>1,'source'=>'System','is_system'=>1],
        ['rule_key'=>'admin_file_organization','label'=>'Datei umbenannt oder verschoben','category'=>'admin_review','rule_type'=>'system','source_field'=>'current_path','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Datei wurde organisiert','points'=>1,'source'=>'System','is_system'=>1],
        ['rule_key'=>'special_collection','label'=>'Besondere Sammlung / Archivordner','category'=>'special_collection','rule_type'=>'system','source_field'=>'current_path','evaluation_source'=>'system','check_type'=>'none','min_value'=>0,'meaning'=>'Dokument liegt in einer besonderen Sammlung','points'=>10,'source'=>'System','is_system'=>1],
        ['rule_key'=>'manual_archive_research','label'=>'Recherche in Archiven','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_collection_indexing','label'=>'Erschließung von Beständen','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_event_organization','label'=>'Organisation Veranstaltung','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_excursion_organization','label'=>'Organisation Busfahrt / Exkursion','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_exhibition_work','label'=>'Mitarbeit an Ausstellung','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_digitization_support','label'=>'Digitalisierungshilfe','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_lecture_guided_tour','label'=>'Vortrag / Führung','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
        ['rule_key'=>'manual_other','label'=>'Sonstige Tätigkeit','category'=>'manual','rule_type'=>'manual','source_field'=>'manual','evaluation_source'=>'manual','check_type'=>'none','min_value'=>0,'meaning'=>'Manuelle Zusatzpunkte','points'=>0,'source'=>'manuell','is_system'=>0],
    ]);
}

function sanitize_email_list(array $recipients): array
{
    $out = [];
    $seen = [];
    foreach ($recipients as $email) {
        $email = trim((string)$email);
        if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
            continue;
        }
        $key = strtolower($email);
        if (!isset($seen[$key])) {
            $seen[$key] = true;
            $out[] = $email;
        }
    }
    return $out;
}

function mail_header_encode(string $text): string
{
    if (function_exists('mb_encode_mimeheader')) {
        return mb_encode_mimeheader($text, 'UTF-8', 'B');
    }
    return '=?UTF-8?B?' . base64_encode($text) . '?=';
}


function normalize_local_path_for_share(string $path): string
{
    $path = trim(str_replace('\\', '/', $path));
    $path = preg_replace('#/+#', '/', $path);
    return rtrim($path, '/');
}

function build_nextcloud_remote_path(string $localFilePath, string $localBasePath): string
{
    $file = normalize_local_path_for_share($localFilePath);
    $base = normalize_local_path_for_share($localBasePath);

    if ($file === '' || $base === '') {
        throw new RuntimeException('Lokaler Dateipfad oder Nextcloud-Stammverzeichnis fehlt');
    }

    $fileLower = strtolower($file);
    $baseLower = strtolower($base);

    if ($fileLower === $baseLower) {
        throw new RuntimeException('Es wurde kein Dateipfad innerhalb des Nextcloud-Stammverzeichnisses übergeben');
    }

    if (!str_starts_with($fileLower, rtrim($baseLower, '/') . '/')) {
        throw new RuntimeException('Die Datei liegt nicht unterhalb des übergebenen Nextcloud-Stammverzeichnisses');
    }

    $relative = substr($file, strlen(rtrim($base, '/')) + 1);
    $relative = ltrim($relative, '/');

    $remoteBase = trim((string)env_value('NEXTCLOUD_REMOTE_BASE', ''), "/ \t\n\r\0\x0B");
    $remote = '/' . ($remoteBase !== '' ? $remoteBase . '/' : '') . $relative;
    $remote = preg_replace('#/+#', '/', $remote);
    return $remote;
}

function nextcloud_download_url_from_share_url(string $shareUrl): string
{
    $shareUrl = rtrim(trim($shareUrl), '/');
    if ($shareUrl === '') {
        return '';
    }
    // Bei Nextcloud-Freigaben ist /download der übliche Direktdownload-Endpunkt.
    return $shareUrl . '/download';
}

function create_nextcloud_public_share(string $remotePath): array
{
    $baseUrl = rtrim((string)env_value('NEXTCLOUD_BASE_URL', ''), '/');
    $username = (string)env_value('NEXTCLOUD_USERNAME', '');
    $password = (string)env_value('NEXTCLOUD_APP_PASSWORD', '');

    if ($baseUrl === '' || $username === '' || $password === '') {
        throw new RuntimeException('Nextcloud-Zugangsdaten sind in der .env nicht vollständig gesetzt');
    }

    if (!function_exists('curl_init')) {
        throw new RuntimeException('PHP-cURL ist auf dem Server nicht verfügbar');
    }

    $url = $baseUrl . '/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json';
    $postFields = http_build_query([
        'path' => $remotePath,
        'shareType' => 3,       // public link
        'permissions' => 1,     // read
    ]);

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $postFields,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPAUTH => CURLAUTH_BASIC,
        CURLOPT_USERPWD => $username . ':' . $password,
        CURLOPT_HTTPHEADER => [
            'OCS-APIRequest: true',
            'Accept: application/json',
            'Content-Type: application/x-www-form-urlencoded',
        ],
        CURLOPT_TIMEOUT => 25,
    ]);

    $raw = curl_exec($ch);
    $errno = curl_errno($ch);
    $error = curl_error($ch);
    $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($raw === false || $errno !== 0) {
        throw new RuntimeException('Nextcloud-Verbindung fehlgeschlagen: ' . $error);
    }

    $data = json_decode((string)$raw, true);
    if (!is_array($data)) {
        throw new RuntimeException('Nextcloud lieferte keine gültige JSON-Antwort');
    }

    $ocs = $data['ocs'] ?? [];
    $meta = is_array($ocs) ? ($ocs['meta'] ?? []) : [];
    $payload = is_array($ocs) ? ($ocs['data'] ?? []) : [];
    $statusCode = (int)($meta['statuscode'] ?? 0);

    if ($httpCode >= 400 || ($statusCode !== 100 && $statusCode !== 200)) {
        $message = (string)($meta['message'] ?? 'Nextcloud-Freigabe konnte nicht erstellt werden');
        throw new RuntimeException($message);
    }

    $shareUrl = (string)($payload['url'] ?? '');
    if ($shareUrl === '') {
        throw new RuntimeException('Nextcloud hat keinen Freigabelink geliefert');
    }

    return [
        'remote_path' => $remotePath,
        'share_url' => $shareUrl,
        'download_url' => nextcloud_download_url_from_share_url($shareUrl),
    ];
}

if ($method === 'POST' && $path === '/api/nextcloud/share') {
    $currentUser = require_role(['admin', 'superadmin']);
    $input = get_json_input();
    $localFilePath = trim((string)($input['local_file_path'] ?? ''));
    $localBasePath = trim((string)($input['local_nextcloud_base'] ?? ''));

    try {
        $remotePath = build_nextcloud_remote_path($localFilePath, $localBasePath);
        $share = create_nextcloud_public_share($remotePath);
        api_log('info', 'Nextcloud-Freigabelink erzeugt', [
            'by_user_id' => $currentUser['id'],
            'remote_path' => $remotePath,
        ]);
        json_response([
            'success' => true,
            'remote_path' => $share['remote_path'],
            'share_url' => $share['share_url'],
            'download_url' => $share['download_url'],
        ]);
    } catch (Throwable $e) {
        api_log('error', 'Nextcloud-Freigabelink konnte nicht erzeugt werden', [
            'by_user_id' => $currentUser['id'],
            'error' => $e->getMessage(),
        ]);
        json_response(['success' => false, 'error' => $e->getMessage()], 500);
    }
}

function send_text_mail(string $to, string $subject, string $body, array $attachments = []): bool
{
    $from = env_value('MAIL_FROM', 'noreply@ortschronik.info');
    $fromName = env_value('MAIL_FROM_NAME', 'Ortschronik');
    $replyTo = env_value('MAIL_REPLY_TO', $from);
    $encodedSubject = mail_header_encode($subject);
    $encodedFromName = mail_header_encode($fromName ?: 'Ortschronik');

    $headers = [];
    $headers[] = "From: {$encodedFromName} <{$from}>";
    $headers[] = "Reply-To: {$replyTo}";
    $headers[] = "MIME-Version: 1.0";
    $headers[] = "X-Mailer: Ortschronik-Uploader";

    if (!empty($attachments)) {
        $boundary = '=_ortschronik_' . bin2hex(random_bytes(12));
        $message = "--{$boundary}\r\n";
        $message .= "Content-Type: text/plain; charset=UTF-8\r\n";
        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";
        $message .= $body . "\r\n\r\n";

        foreach ($attachments as $attachment) {
            if (!is_array($attachment) || empty($attachment['content_base64'])) {
                continue;
            }
            $filename = preg_replace('/[\r\n"]+/', '_', (string)($attachment['filename'] ?? 'anlage.dat'));
            $mime = preg_replace('/[\r\n"]+/', '', (string)($attachment['mime_type'] ?? 'application/octet-stream'));
            $content = chunk_split((string)$attachment['content_base64']);
            $message .= "--{$boundary}\r\n";
            $message .= "Content-Type: {$mime}; name=\"{$filename}\"\r\n";
            $message .= "Content-Transfer-Encoding: base64\r\n";
            $message .= "Content-Disposition: attachment; filename=\"{$filename}\"\r\n\r\n";
            $message .= $content . "\r\n";
        }

        $message .= "--{$boundary}--\r\n";
        $headers[] = "Content-Type: multipart/mixed; boundary=\"{$boundary}\"";
        return mail($to, $encodedSubject, $message, implode("\r\n", $headers));
    }

    $headers[] = "Content-Type: text/plain; charset=UTF-8";
    $headers[] = "Content-Transfer-Encoding: 8bit";
    return mail($to, $encodedSubject, $body, implode("\r\n", $headers));
}

if ($method === 'POST' && $path === '/api/mails/send') {
    $currentUser = require_role(['admin', 'superadmin']);
    $input = get_json_input();
    $recipients = sanitize_email_list(is_array($input['recipients'] ?? null) ? $input['recipients'] : []);
    $subject = trim((string)($input['subject'] ?? ''));
    $body = (string)($input['body'] ?? '');
    $mode = trim((string)($input['mode'] ?? 'none'));
    if (!in_array($mode, ['none', 'link', 'attachment'], true)) {
        json_response(['success' => false, 'error' => 'Ungültige Versandart'], 400);
    }
    $link = trim((string)($input['link'] ?? ''));
    $attachments = [];

    if (!$recipients) {
        json_response(['success' => false, 'error' => 'Keine gültigen Empfänger'], 400);
    }
    if ($subject === '') {
        json_response(['success' => false, 'error' => 'Betreff fehlt'], 400);
    }
    if (trim($body) === '') {
        json_response(['success' => false, 'error' => 'Nachrichtentext fehlt'], 400);
    }
    if ($mode === 'link' && $link === '') {
        $localFilePath = trim((string)($input['local_file_path'] ?? ''));
        $localBasePath = trim((string)($input['local_nextcloud_base'] ?? ''));
        if ($localFilePath !== '' && $localBasePath !== '') {
            try {
                $remotePath = build_nextcloud_remote_path($localFilePath, $localBasePath);
                $share = create_nextcloud_public_share($remotePath);
                $link = $share['download_url'] ?: $share['share_url'];
                $body = str_replace('{link}', $link, $body);
                if (strpos($body, $link) === false) {
                    $body .= "

Downloadlink:
" . $link;
                }
            } catch (Throwable $e) {
                api_log('error', 'Nextcloud-Link für Rundmail konnte nicht erzeugt werden', ['error' => $e->getMessage()]);
                json_response(['success' => false, 'error' => 'Nextcloud-Link konnte nicht erzeugt werden: ' . $e->getMessage()], 500);
            }
        }
    }

    if ($mode === 'link' && trim($link) === '' && strpos($body, 'http') === false) {
        json_response(['success' => false, 'error' => 'Für Versandart Link fehlt der Nextcloud-Link'], 400);
    }

    if ($mode === 'attachment') {
        $candidateAttachments = [];
        if (is_array($input['attachments'] ?? null)) {
            $candidateAttachments = $input['attachments'];
        } elseif (is_array($input['attachment'] ?? null)) {
            $candidateAttachments = [$input['attachment']];
        }
        if (!$candidateAttachments) {
            json_response(['success' => false, 'error' => 'Anlage fehlt'], 400);
        }
        $totalSize = 0;
        foreach ($candidateAttachments as $attachment) {
            if (!is_array($attachment) || empty($attachment['content_base64'])) {
                continue;
            }
            $raw = base64_decode((string)$attachment['content_base64'], true);
            if ($raw === false) {
                json_response(['success' => false, 'error' => 'Eine Anlage ist ungültig kodiert'], 400);
            }
            $size = strlen($raw);
            if ($size > 8 * 1024 * 1024) {
                json_response(['success' => false, 'error' => 'Eine Anlage ist größer als 8 MB. Bitte als Link versenden.'], 400);
            }
            $totalSize += $size;
            if ($totalSize > 12 * 1024 * 1024) {
                json_response(['success' => false, 'error' => 'Die Anlagen sind zusammen größer als 12 MB. Bitte als Link versenden.'], 400);
            }
            $attachment['content_base64'] = base64_encode($raw);
            $attachments[] = $attachment;
        }
        if (!$attachments) {
            json_response(['success' => false, 'error' => 'Keine gültige Anlage gefunden'], 400);
        }
    }

    $sent = 0;
    $failed = 0;
    $failedRecipients = [];
    foreach ($recipients as $recipient) {
        $ok = send_text_mail($recipient, $subject, $body, $attachments);
        if ($ok) {
            $sent++;
        } else {
            $failed++;
            $failedRecipients[] = $recipient;
        }
    }
    try {
        $pdo = db();
        ensure_mail_history_table($pdo);
        $docs = [];
        if (is_array($input['documents'] ?? null)) {
            $docs = $input['documents'];
        }
        if ($link !== '') {
            $docs[] = ['link' => $link];
        }
        if ($attachments) {
            foreach ($attachments as $attachment) {
                $docs[] = ['attachment' => (string)($attachment['filename'] ?? 'Anhang')];
            }
        }
        $hist = $pdo->prepare("INSERT INTO mail_history (sent_by_user_id, sent_by_name, recipient_email, subject, body_preview, mode, status, error_message, documents_json) VALUES (:uid, :uname, :recipient, :subject, :body_preview, :mode, :status, :error_message, :documents_json)");
        foreach ($recipients as $recipient) {
            $isFailed = in_array($recipient, $failedRecipients, true);
            $hist->execute([
                ':uid' => $currentUser['id'],
                ':uname' => $currentUser['display_name'],
                ':recipient' => $recipient,
                ':subject' => $subject,
                ':body_preview' => (function_exists('mb_substr') ? mb_substr($body, 0, 1000) : substr($body, 0, 1000)),
                ':mode' => $mode,
                ':status' => $isFailed ? 'failed' : 'sent',
                ':error_message' => $isFailed ? 'mail() fehlgeschlagen' : null,
                ':documents_json' => json_encode($docs, JSON_UNESCAPED_UNICODE),
            ]);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Mail-Historie konnte nicht geschrieben werden', ['error' => $e->getMessage()]);
    }

    api_log($failed > 0 ? 'warning' : 'info', 'Rundmail versendet', [
        'by_user_id' => $currentUser['id'],
        'recipient_count' => count($recipients),
        'sent' => $sent,
        'failed' => $failed,
        'mode' => $mode,
        'attachment_count' => count($attachments),
        'subject' => $subject,
    ]);
    json_response([
        'success' => $sent > 0,
        'message' => 'Rundmail-Versand abgeschlossen',
        'sent' => $sent,
        'failed' => $failed,
        'failed_recipients' => $failedRecipients,
    ], $sent > 0 ? 200 : 500);
}


if ($method === 'GET' && $path === '/api/mails/history') {
    $currentUser = require_role(['admin', 'superadmin']);
    $limit = max(1, min(1000, (int)($_GET['limit'] ?? 200)));
    $pdo = db();
    ensure_mail_history_table($pdo);
    $stmt = $pdo->prepare("SELECT id, sent_at, sent_by_user_id, sent_by_name AS sender_name, recipient_email, subject, body_preview, mode, status, error_message, documents_json FROM mail_history ORDER BY sent_at DESC, id DESC LIMIT " . $limit);
    $stmt->execute();
    $items = [];
    foreach ($stmt->fetchAll() as $row) {
        $docs = [];
        if (!empty($row['documents_json'])) {
            $decoded = json_decode((string)$row['documents_json'], true);
            if (is_array($decoded)) { $docs = $decoded; }
        }
        $row['documents'] = $docs;
        unset($row['documents_json']);
        $items[] = $row;
    }
    json_response(['success' => true, 'items' => $items]);
}


require_once __DIR__ . '/routes_admin_endpoints.php';
require_once __DIR__ . '/routes_points.php';
require_once __DIR__ . '/routes_mail_groups.php';

json_response([
    'success' => false,
    'error' => 'Route nicht gefunden',
    'path' => $path
], 404);
