<?php
declare(strict_types=1);


if (!function_exists('user_has_folder_permission')) {


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
    return ['hochgeladen', 'erfasst', 'geaendert', 'rueckfrage', 'geprueft', 'archiviert'];
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

}
