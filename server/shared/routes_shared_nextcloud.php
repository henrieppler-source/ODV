<?php

declare(strict_types=1);

function server_env_value(string $key, string $default = ''): string
{
    $value = getenv($key);
    if ($value !== false && trim((string)$value) !== '') {
        return trim((string)$value);
    }
    static $env = null;
    if ($env === null) {
        $env = [];
        $path = __DIR__ . '/.env';
        if (is_file($path) && is_readable($path)) {
            foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
                $line = trim((string)$line);
                if ($line === '' || str_starts_with($line, '#') || strpos($line, '=') === false) {
                    continue;
                }
                [$name, $rawValue] = explode('=', $line, 2);
                $env[trim($name)] = trim(trim($rawValue), "\"'");
            }
        }
    }
    return trim((string)($env[$key] ?? $default));
}

function nextcloud_base_url(PDO $pdo): string
{
    $webUrl = trim((string)(setting_get($pdo, 'nextcloud_base_url', '') ?? ''));
    if ($webUrl === '') {
        $webUrl = server_env_value('NEXTCLOUD_BASE_URL');
    }
    if ($webUrl === '') {
        $webUrl = 'https://nx94165.your-storageshare.de';
    }
    $parts = parse_url($webUrl);
    if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) {
        throw new RuntimeException('Nextcloud-Basis-URL ist ungültig.');
    }
    $base = $parts['scheme'] . '://' . $parts['host'];
    if (!empty($parts['port'])) {
        $base .= ':' . $parts['port'];
    }
    $path = (string)($parts['path'] ?? '');
    $marker = '/apps/files';
    $pos = strpos($path, $marker);
    if ($pos !== false) {
        $prefix = substr($path, 0, $pos);
        if ($prefix !== '') {
            $base .= rtrim($prefix, '/');
        }
    }
    return rtrim($base, '/');
}

function nextcloud_remote_base_from_web_files_url(PDO $pdo): string
{
    $webUrl = trim((string)(setting_get($pdo, 'nextcloud_web_files_url', '') ?? ''));
    if ($webUrl === '') {
        return '';
    }
    $parts = parse_url($webUrl);
    if (!is_array($parts) || empty($parts['query'])) {
        return '';
    }
    parse_str((string)$parts['query'], $query);
    $dir = trim(str_replace('\\', '/', (string)($query['dir'] ?? '')), '/');
    return $dir;
}

function nextcloud_credentials_for_user(PDO $pdo, array $user): array
{
    $systemUsername = trim((string)(setting_get($pdo, 'nextcloud_technical_username', '') ?? ''));
    $systemPasswordEnc = trim((string)(setting_get($pdo, 'nextcloud_technical_password_enc', '') ?? ''));
    if ($systemUsername !== '' && $systemPasswordEnc !== '') {
        $systemPassword = decrypt_nextcloud_credential($pdo, $systemPasswordEnc);
        if ($systemPassword !== '') {
            return [
                'username' => $systemUsername,
                'password' => $systemPassword,
                'source_user_id' => 0,
                'source_role' => 'system',
            ];
        }
    }

    $envUsername = server_env_value('NEXTCLOUD_USERNAME');
    $envPassword = server_env_value('NEXTCLOUD_APP_PASSWORD');
    if ($envUsername !== '' && $envPassword !== '') {
        return [
            'username' => $envUsername,
            'password' => $envPassword,
            'source_user_id' => 0,
            'source_role' => 'system',
        ];
    }

    ensure_user_nextcloud_columns($pdo);
    $stmt = $pdo->prepare("SELECT id, username, display_name, role, nextcloud_username, nextcloud_password_enc FROM users WHERE id = :id LIMIT 1");
    $stmt->execute([':id' => (int)($user['id'] ?? 0)]);
    $row = $stmt->fetch();

    $candidates = [];
    if (is_array($row)) {
        $candidates[] = $row;
    }

    $fallback = $pdo->query("
        SELECT id, username, display_name, role, nextcloud_username, nextcloud_password_enc
        FROM users
        WHERE is_active = 1
          AND role IN ('superadmin', 'admin')
          AND COALESCE(nextcloud_username, '') <> ''
          AND COALESCE(nextcloud_password_enc, '') <> ''
        ORDER BY FIELD(role, 'superadmin', 'admin'), id ASC
    ");
    foreach ($fallback->fetchAll() as $candidate) {
        if ((int)($candidate['id'] ?? 0) === (int)($user['id'] ?? 0)) {
            continue;
        }
        $candidates[] = $candidate;
    }

    foreach ($candidates as $candidate) {
        $username = trim((string)($candidate['nextcloud_username'] ?? ''));
        $passwordEnc = trim((string)($candidate['nextcloud_password_enc'] ?? ''));
        if ($username === '' || $passwordEnc === '') {
            continue;
        }
        $password = decrypt_nextcloud_credential($pdo, $passwordEnc);
        if ($password === '') {
            continue;
        }
        return [
            'username' => $username,
            'password' => $password,
            'source_user_id' => (int)($candidate['id'] ?? 0),
            'source_role' => (string)($candidate['role'] ?? ''),
        ];
    }

    throw new RuntimeException('Es sind keine technischen Nextcloud-Zugangsdaten, keine .env-Zugangsdaten und keine Benutzer-Zugangsdaten gespeichert.');
}

function nextcloud_ocs_request(string $method, string $url, string $username, string $password, array $data = []): array
{
    $body = http_build_query($data);
    $headers = [
        'OCS-APIRequest: true',
        'Accept: application/json',
        'Content-Type: application/x-www-form-urlencoded',
    ];
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, strtoupper($method));
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_USERPWD, $username . ':' . $password);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        if ($body !== '') {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        $raw = curl_exec($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        if ($raw === false) {
            throw new RuntimeException('Nextcloud-API nicht erreichbar: ' . $error);
        }
    } else {
        $headers[] = 'Authorization: Basic ' . base64_encode($username . ':' . $password);
        $context = stream_context_create([
            'http' => [
                'method' => strtoupper($method),
                'header' => implode("\r\n", $headers),
                'content' => $body,
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ]);
        $raw = file_get_contents($url, false, $context);
        $status = 0;
        foreach (($http_response_header ?? []) as $header) {
            if (preg_match('#^HTTP/\S+\s+(\d+)#', $header, $matches)) {
                $status = (int)$matches[1];
                break;
            }
        }
        if ($raw === false) {
            throw new RuntimeException('Nextcloud-API nicht erreichbar.');
        }
    }
    $decoded = json_decode((string)$raw, true);
    if (!is_array($decoded)) {
        throw new RuntimeException('Nextcloud-API hat keine gültige JSON-Antwort geliefert.');
    }
    $ocs = $decoded['ocs'] ?? null;
    if (!is_array($ocs)) {
        throw new RuntimeException('Nextcloud-API-Antwort hat ein unerwartetes Format.');
    }
    $meta = is_array($ocs['meta'] ?? null) ? $ocs['meta'] : [];
    $statusCode = (int)($meta['statuscode'] ?? 0);
    if ($status >= 400 || !in_array($statusCode, [100, 200], true)) {
        $message = trim((string)($meta['message'] ?? 'Unbekannter Nextcloud-Fehler'));
        throw new RuntimeException($message !== '' ? $message : 'Nextcloud-Freigabe konnte nicht erstellt werden.');
    }
    return $ocs;
}

function nextcloud_webdav_request(string $method, string $url, string $username, string $password, string $body = '', array $extraHeaders = []): string
{
    $headers = array_merge([
        'Accept: application/xml',
    ], $extraHeaders);
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, strtoupper($method));
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_USERPWD, $username . ':' . $password);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        if ($body !== '') {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        $raw = curl_exec($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        if ($raw === false) {
            throw new RuntimeException('Nextcloud-WebDAV nicht erreichbar: ' . $error);
        }
    } else {
        $streamHeaders = $headers;
        $streamHeaders[] = 'Authorization: Basic ' . base64_encode($username . ':' . $password);
        $context = stream_context_create([
            'http' => [
                'method' => strtoupper($method),
                'header' => implode("\r\n", $streamHeaders),
                'content' => $body,
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ]);
        $raw = file_get_contents($url, false, $context);
        $status = 0;
        foreach (($http_response_header ?? []) as $header) {
            if (preg_match('#^HTTP/\S+\s+(\d+)#', $header, $matches)) {
                $status = (int)$matches[1];
                break;
            }
        }
        if ($raw === false) {
            throw new RuntimeException('Nextcloud-WebDAV nicht erreichbar.');
        }
    }
    if ($status < 200 || $status >= 300) {
        throw new RuntimeException('Nextcloud-WebDAV antwortet mit HTTP ' . $status . '.');
    }
    return (string)$raw;
}

function create_nextcloud_public_share(string $remotePath, string $expiresAt = '', ?array $currentUser = null): array
{
    $path = trim(str_replace('\\', '/', $remotePath));
    $pdo = db();
    if ($path === '') {
        throw new RuntimeException('Nextcloud-Dateipfad fehlt.');
    }
    if ($currentUser === null) {
        $currentUser = current_user();
    }
    $credentials = nextcloud_credentials_for_user($pdo, $currentUser);
    $baseUrl = nextcloud_base_url($pdo);
    $remoteBase = trim(str_replace('\\', '/', (string)(setting_get($pdo, 'nextcloud_remote_base', '') ?? '')), '/');
    if ($remoteBase === '') {
        $remoteBase = nextcloud_remote_base_from_web_files_url($pdo);
    }
    if ($remoteBase === '') {
        $remoteBase = trim(str_replace('\\', '/', server_env_value('NEXTCLOUD_REMOTE_BASE')), '/');
    }
    $sharePath = '/' . ltrim(($remoteBase !== '' ? $remoteBase . '/' : '') . ltrim($path, '/'), '/');
    $payload = [
        'path' => $sharePath,
        'shareType' => '3',
        'permissions' => '1',
    ];
    $expiresAt = trim($expiresAt);
    if ($expiresAt !== '') {
        $payload['expireDate'] = $expiresAt;
    }
    $ocs = nextcloud_ocs_request(
        'POST',
        $baseUrl . '/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json',
        $credentials['username'],
        $credentials['password'],
        $payload
    );
    $data = is_array($ocs['data'] ?? null) ? $ocs['data'] : [];
    $shareUrl = trim((string)($data['url'] ?? ''));
    if ($shareUrl === '') {
        throw new RuntimeException('Nextcloud hat keinen Freigabelink zurückgegeben.');
    }
    $downloadUrl = rtrim($shareUrl, '/') . '/download';
    $result = ['share_url' => $shareUrl, 'download_url' => $downloadUrl, 'url' => $downloadUrl];
    if ($expiresAt !== '') {
        $result['expires_at'] = $expiresAt;
    }
    return $result;
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

