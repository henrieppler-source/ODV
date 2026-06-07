<?php

declare(strict_types=1);

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

    $stmt = $pdo->prepare("
        SELECT
            t.id AS token_id,
            t.expires_at,
            u.id,
            u.username,
            u.display_name,
            u.email,
            u.role,
            u.place,
            u.is_active
        FROM api_tokens t
        INNER JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = :token_hash
        LIMIT 1
    ");

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
