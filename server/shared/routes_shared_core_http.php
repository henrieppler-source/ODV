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

function client_ip(): string

{

    return (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');

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
