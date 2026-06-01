<?php
declare(strict_types=1);

function mail_group_visible_to_user(array $viewer, array $group): bool
{
    $viewerRole = role_key($viewer);
    $creatorRole = strtolower(trim((string)($group['created_by_role'] ?? '')));
    $creatorUserId = (int)($group['created_by_user_id'] ?? 0);
    $creatorPlace = trim((string)($group['created_by_place'] ?? ''));
    $viewerPlace = trim((string)($viewer['place'] ?? ''));

    if (in_array($viewerRole, ['admin', 'superadmin'], true)) {
        if ($creatorRole === '' && $creatorUserId <= 0 && $creatorPlace === '') {
            return true;
        }
        return in_array($creatorRole, ['admin', 'superadmin'], true);
    }

    if ($creatorUserId > 0 && $creatorUserId === (int)($viewer['id'] ?? 0)) {
        return true;
    }
    if ($creatorPlace !== '' && $viewerPlace !== '' && mb_strtolower($creatorPlace, 'UTF-8') === mb_strtolower($viewerPlace, 'UTF-8')) {
        return !in_array($creatorRole, ['admin', 'superadmin'], true);
    }
    return false;
}

function mail_group_payload_from_row(array $group): array
{
    return [
        'id' => (int)($group['id'] ?? 0),
        'name' => (string)($group['name'] ?? ''),
        'description' => (string)($group['description'] ?? ''),
        'is_active' => (int)($group['is_active'] ?? 1),
        'created_by_user_id' => isset($group['created_by_user_id']) ? (int)$group['created_by_user_id'] : null,
        'created_by_display_name' => (string)($group['created_by_display_name'] ?? ''),
        'created_by_role' => (string)($group['created_by_role'] ?? ''),
        'created_by_place' => (string)($group['created_by_place'] ?? ''),
        'updated_by_user_id' => isset($group['updated_by_user_id']) ? (int)$group['updated_by_user_id'] : null,
        'created_at' => (string)($group['created_at'] ?? ''),
        'updated_at' => (string)($group['updated_at'] ?? ''),
        'members' => $group['members'] ?? [],
        'external_members' => $group['external_members'] ?? [],
    ];
}

function mail_groups_load_with_members(PDO $pdo): array
{
    ensure_mail_group_external_table($pdo);
    ensure_mail_group_creator_columns($pdo);
    $groupsStmt = $pdo->query("SELECT id, name, description, is_active, created_by_user_id, created_by_display_name, created_by_role, created_by_place, updated_by_user_id, created_at, updated_at FROM mail_groups ORDER BY name ASC");
    $groups = $groupsStmt->fetchAll();

    $membersStmt = $pdo->query("
        SELECT mgm.group_id, u.id AS user_id, u.display_name, u.username, u.email, u.role, u.place, u.is_active
        FROM mail_group_members mgm
        INNER JOIN users u ON u.id = mgm.user_id
        ORDER BY u.display_name ASC, u.username ASC
    ");
    $membersByGroup = [];
    foreach ($membersStmt->fetchAll() as $m) {
        $gid = (int)$m['group_id'];
        $membersByGroup[$gid][] = $m;
    }

    $externalStmt = $pdo->query("SELECT group_id, id, first_name, last_name, email, is_active FROM mail_group_external_members WHERE is_active=1 ORDER BY last_name ASC, first_name ASC, email ASC");
    $externalByGroup = [];
    foreach ($externalStmt->fetchAll() as $m) {
        $gid = (int)$m['group_id'];
        $m['member_type'] = 'external';
        $externalByGroup[$gid][] = $m;
    }

    foreach ($groups as &$g) {
        $gid = (int)$g['id'];
        $g['members'] = $membersByGroup[$gid] ?? [];
        $g['external_members'] = $externalByGroup[$gid] ?? [];
    }
    return $groups;
}

if ($method === 'GET' && $path === '/api/mail-groups') {
    $currentUser = current_user();
    $pdo = db();
    $groups = mail_groups_load_with_members($pdo);
    $filtered = [];
    foreach ($groups as $group) {
        if (mail_group_visible_to_user($currentUser, $group)) {
            $filtered[] = $group;
        }
    }
    json_response(['success' => true, 'groups' => $filtered]);
}

if ($method === 'PUT' && $path === '/api/mail-groups') {
    $currentUser = current_user();
    $currentRole = role_key($currentUser);
    $input = get_json_input();
    $groups = $input['groups'] ?? null;
    if (!is_array($groups)) {
        json_response(['success' => false, 'error' => 'groups muss ein Array sein'], 400);
    }
    $pdo = db();
    ensure_mail_group_external_table($pdo);
    ensure_mail_group_creator_columns($pdo);
    try {
        $pdo->beginTransaction();
        $seenIds = [];
        foreach ($groups as $group) {
            if (!is_array($group)) {
                continue;
            }
            $id = (int)($group['id'] ?? 0);
            $name = trim((string)($group['name'] ?? ''));
            $description = trim((string)($group['description'] ?? ''));
            $isActive = isset($group['is_active']) ? (int)(bool)$group['is_active'] : 1;
            $members = $group['member_user_ids'] ?? [];
            $externalMembers = $group['external_members'] ?? [];
            if ($name === '') {
                continue;
            }

            if ($id > 0) {
                $existingStmt = $pdo->prepare("SELECT id, created_by_user_id, created_by_role, created_by_place FROM mail_groups WHERE id = :id LIMIT 1");
                $existingStmt->execute([':id' => $id]);
                $existing = $existingStmt->fetch();
                if (!$existing) {
                    json_response(['success' => false, 'error' => 'Verteiler nicht gefunden'], 404);
                }
                if (!mail_group_visible_to_user($currentUser, $existing)) {
                    json_response(['success' => false, 'error' => 'Keine Berechtigung für diesen Verteiler'], 403);
                }
                $stmt = $pdo->prepare("UPDATE mail_groups SET name=:name, description=:description, is_active=:is_active, updated_by_user_id=:uid WHERE id=:id");
                $stmt->execute([
                    ':id' => $id,
                    ':name' => $name,
                    ':description' => $description !== '' ? $description : null,
                    ':is_active' => $isActive,
                    ':uid' => $currentUser['id'],
                ]);
            } else {
                $stmt = $pdo->prepare("INSERT INTO mail_groups (name, description, is_active, created_by_user_id, created_by_display_name, created_by_role, created_by_place, updated_by_user_id) VALUES (:name, :description, :is_active, :created_by_user_id, :created_by_display_name, :created_by_role, :created_by_place, :updated_by_user_id)");
                $stmt->execute([
                    ':name' => $name,
                    ':description' => $description !== '' ? $description : null,
                    ':is_active' => $isActive,
                    ':created_by_user_id' => (int)$currentUser['id'],
                    ':created_by_display_name' => (string)$currentUser['display_name'],
                    ':created_by_role' => $currentRole,
                    ':created_by_place' => (string)($currentUser['place'] ?? ''),
                    ':updated_by_user_id' => (int)$currentUser['id'],
                ]);
                $id = (int)$pdo->lastInsertId();
            }

            $seenIds[] = $id;
            $pdo->prepare("DELETE FROM mail_group_members WHERE group_id=:id")->execute([':id' => $id]);
            $pdo->prepare("DELETE FROM mail_group_external_members WHERE group_id=:id")->execute([':id' => $id]);
            $ins = $pdo->prepare("INSERT INTO mail_group_members (group_id, user_id) VALUES (:gid, :uid)");
            if (is_array($members)) {
                foreach ($members as $mid) {
                    $mid = (int)$mid;
                    if ($mid > 0) {
                        $ins->execute([':gid' => $id, ':uid' => $mid]);
                    }
                }
            }
            if (is_array($externalMembers) && in_array($currentRole, ['admin', 'superadmin'], true)) {
                $insExt = $pdo->prepare("INSERT INTO mail_group_external_members (group_id, first_name, last_name, email, is_active) VALUES (:gid, :first_name, :last_name, :email, :active)");
                foreach ($externalMembers as $ext) {
                    if (!is_array($ext)) {
                        continue;
                    }
                    $email = trim((string)($ext['email'] ?? ''));
                    if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
                        continue;
                    }
                    $insExt->execute([
                        ':gid' => $id,
                        ':first_name' => trim((string)($ext['first_name'] ?? '')),
                        ':last_name' => trim((string)($ext['last_name'] ?? '')),
                        ':email' => $email,
                        ':active' => !empty($ext['is_active']) ? 1 : 1,
                    ]);
                }
            }
        }
        $pdo->commit();
        api_log('info', 'Mail-Verteiler gespeichert', ['by_user_id' => $currentUser['id'], 'count' => count($seenIds)]);
        $groups = mail_groups_load_with_members($pdo);
        $filtered = [];
        foreach ($groups as $group) {
            if (mail_group_visible_to_user($currentUser, $group)) {
                $filtered[] = $group;
            }
        }
        json_response(['success' => true, 'message' => 'Verteiler wurden gespeichert', 'groups' => $filtered]);
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        api_log('error', 'Mail-Verteiler konnten nicht gespeichert werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Verteiler konnten nicht gespeichert werden'], 500);
    }
}
