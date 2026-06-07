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

    $stmt = $pdo->prepare("\n        SELECT\n            t.id AS token_id,\n            t.expires_at,\n            u.id,\n            u.username,\n            u.display_name,\n            u.email,\n            u.role,\n            u.place,\n            u.is_active\n        FROM api_tokens t\n        INNER JOIN users u ON u.id = t.user_id\n        WHERE t.token_hash = :token_hash\n        LIMIT 1\n    ");

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



function sanitize_email_list(array $emails): array

{

    $cleaned = [];

    $seen = [];

    foreach ($emails as $email) {

        $email = trim((string)$email);

        if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {

            continue;

        }

        $key = strtolower($email);

        if (isset($seen[$key])) {

            continue;

        }

        $seen[$key] = true;

        $cleaned[] = $email;

    }

    return $cleaned;

}



function send_text_mail(string $to, string $subject, string $body, array $attachments = [], string $replyTo = '', string $bodyHtml = ''): bool

{

    $recipient = trim($to);

    if ($recipient === '') {

        return false;

    }

    if (function_exists('mb_encode_mimeheader')) {

        $encodedSubject = mb_encode_mimeheader($subject, 'UTF-8', 'Q', "\r\n");

    } else {

        $encodedSubject = '=?UTF-8?B?' . base64_encode($subject) . '?=';

    }

    $headers = [

        'MIME-Version: 1.0',

        'From: Ortschronik <info@ortschronik.info>',

    ];

    $replyTo = trim($replyTo);

    if ($replyTo !== '' && filter_var($replyTo, FILTER_VALIDATE_EMAIL)) {

        $headers[] = 'Reply-To: ' . $replyTo;

    }



    $cleanAttachments = [];

    foreach ($attachments as $attachment) {

        if (!is_array($attachment) || empty($attachment['content_base64'])) {

            continue;

        }

        $cleanAttachments[] = $attachment;

    }



    $hasHtml = trim($bodyHtml) !== '';

    $params = '-f info@ortschronik.info';

    $sendPlainFallback = static function (string $recipient, string $encodedSubject, string $body, array $headers, string $params): bool {

        $plainHeaders = [];

        foreach ($headers as $header) {

            if (stripos($header, 'Content-Type:') === 0 || stripos($header, 'Content-Transfer-Encoding:') === 0) {

                continue;

            }

            $plainHeaders[] = $header;

        }

        $plainHeaders[] = "Content-Type: text/plain; charset=UTF-8";

        $plainHeaders[] = "Content-Transfer-Encoding: 8bit";

        return mail($recipient, $encodedSubject, $body, implode("\r\n", $plainHeaders), $params);

    };



    if ($cleanAttachments) {

        $boundaryMixed = '=_odv_mixed_' . bin2hex(random_bytes(12));

        $buildMixedMessage = static function (bool $includeHtml) use ($boundaryMixed, $body, $bodyHtml, $cleanAttachments): string {

            $message = "This is a multi-part message in MIME format.\r\n";

            $message .= "--{$boundaryMixed}\r\n";

            if ($includeHtml) {

                $boundaryAlt = '=_odv_alt_' . bin2hex(random_bytes(12));

                $message .= "Content-Type: multipart/alternative; boundary=\"{$boundaryAlt}\"\r\n\r\n";

                $message .= "--{$boundaryAlt}\r\n";

                $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $body . "\r\n";

                $message .= "--{$boundaryAlt}\r\n";

                $message .= "Content-Type: text/html; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $bodyHtml . "\r\n";

                $message .= "--{$boundaryAlt}--\r\n";

            } else {

                $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $body . "\r\n";

            }

            foreach ($cleanAttachments as $attachment) {

                $filename = trim((string)($attachment['filename'] ?? 'Anhang'));

                $mime = trim((string)($attachment['mime_type'] ?? 'application/octet-stream'));

                $raw = base64_decode((string)$attachment['content_base64'], true);

                if ($raw === false) {

                    continue;

                }

                $message .= "--{$boundaryMixed}\r\n";

                $message .= "Content-Type: {$mime}; name=\"" . str_replace('"', '\\"', $filename) . "\"\r\n";

                $message .= "Content-Transfer-Encoding: base64\r\n";

                $message .= "Content-Disposition: attachment; filename=\"" . str_replace('"', '\\"', $filename) . "\"\r\n\r\n";

                $message .= chunk_split(base64_encode($raw)) . "\r\n";

            }

            $message .= "--{$boundaryMixed}--\r\n";

            return $message;

        };

        $headersMixed = $headers;

        $headersMixed[] = "Content-Type: multipart/mixed; boundary=\"{$boundaryMixed}\"";

        $message = $buildMixedMessage($hasHtml);

        $sent = mail($recipient, $encodedSubject, $message, implode("\r\n", $headersMixed), $params);

        if (!$sent && $hasHtml) {

            $messageFallback = $buildMixedMessage(false);

            $sent = mail($recipient, $encodedSubject, $messageFallback, implode("\r\n", $headersMixed), $params);

        }

        if (!$sent) {

            $sent = $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

        }

        return $sent;

    }



    if ($hasHtml) {

        $boundary = '=_odv_alt_' . bin2hex(random_bytes(12));

        $headers[] = "Content-Type: multipart/alternative; boundary=\"{$boundary}\"";

        $message = "This is a multi-part message in MIME format.\r\n";

        $message .= "--{$boundary}\r\n";

        $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

        $message .= $body . "\r\n";

        $message .= "--{$boundary}\r\n";

        $message .= "Content-Type: text/html; charset=UTF-8\r\n";

        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

        $message .= $bodyHtml . "\r\n";

        $message .= "--{$boundary}--\r\n";

        $sent = mail($recipient, $encodedSubject, $message, implode("\r\n", $headers), $params);

        if (!$sent) {

            $sent = $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

        }

        return $sent;

    }



    return $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

}

