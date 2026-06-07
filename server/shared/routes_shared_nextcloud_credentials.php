<?php

declare(strict_types=1);

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

