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

