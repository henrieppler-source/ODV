<?php

declare(strict_types=1);

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

