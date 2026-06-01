<?php
declare(strict_types=1);

if ($method === 'GET' && $path === '/api/mail-groups') {
    require_role(['admin', 'superadmin']);
    $pdo = db();
    ensure_mail_group_external_table($pdo);
    $groupsStmt = $pdo->query("SELECT id, name, description, is_active, created_at, updated_at FROM mail_groups ORDER BY name ASC");
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
        if (!isset($membersByGroup[$gid])) {
            $membersByGroup[$gid] = [];
        }
        $membersByGroup[$gid][] = $m;
    }
    $externalStmt = $pdo->query("SELECT group_id, id, first_name, last_name, email, is_active FROM mail_group_external_members WHERE is_active=1 ORDER BY last_name ASC, first_name ASC, email ASC");
    $externalByGroup = [];
    foreach ($externalStmt->fetchAll() as $m) {
        $gid = (int)$m['group_id'];
        if (!isset($externalByGroup[$gid])) { $externalByGroup[$gid] = []; }
        $m['member_type'] = 'external';
        $externalByGroup[$gid][] = $m;
    }
    foreach ($groups as &$g) {
        $gid = (int)$g['id'];
        $g['members'] = $membersByGroup[$gid] ?? [];
        $g['external_members'] = $externalByGroup[$gid] ?? [];
    }
    json_response(['success' => true, 'groups' => $groups]);
}

if ($method === 'PUT' && $path === '/api/mail-groups') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $groups = $input['groups'] ?? null;
    if (!is_array($groups)) {
        json_response(['success' => false, 'error' => 'groups muss ein Array sein'], 400);
    }
    $pdo = db();
    ensure_mail_group_external_table($pdo);
    try {
        $pdo->beginTransaction();
        $seenIds = [];
        foreach ($groups as $group) {
            if (!is_array($group)) { continue; }
            $id = (int)($group['id'] ?? 0);
            $name = trim((string)($group['name'] ?? ''));
            $description = trim((string)($group['description'] ?? ''));
            $isActive = isset($group['is_active']) ? (int)(bool)$group['is_active'] : 1;
            $members = $group['member_user_ids'] ?? [];
            $externalMembers = $group['external_members'] ?? [];
            if ($name === '') { continue; }
            if ($id > 0) {
                $stmt = $pdo->prepare("UPDATE mail_groups SET name=:name, description=:description, is_active=:is_active, updated_by_user_id=:uid WHERE id=:id");
                $stmt->execute([':id'=>$id, ':name'=>$name, ':description'=>$description !== '' ? $description : null, ':is_active'=>$isActive, ':uid'=>$currentUser['id']]);
            } else {
                $stmt = $pdo->prepare("INSERT INTO mail_groups (name, description, is_active, updated_by_user_id) VALUES (:name, :description, :is_active, :uid)");
                $stmt->execute([':name'=>$name, ':description'=>$description !== '' ? $description : null, ':is_active'=>$isActive, ':uid'=>$currentUser['id']]);
                $id = (int)$pdo->lastInsertId();
            }
            $seenIds[] = $id;
            $pdo->prepare("DELETE FROM mail_group_members WHERE group_id=:id")->execute([':id'=>$id]);
            $pdo->prepare("DELETE FROM mail_group_external_members WHERE group_id=:id")->execute([':id'=>$id]);
            $ins = $pdo->prepare("INSERT INTO mail_group_members (group_id, user_id) VALUES (:gid, :uid)");
            if (is_array($members)) {
                foreach ($members as $mid) {
                    $mid = (int)$mid;
                    if ($mid > 0) {
                        $ins->execute([':gid'=>$id, ':uid'=>$mid]);
                    }
                }
            }
            if (is_array($externalMembers)) {
                $insExt = $pdo->prepare("INSERT INTO mail_group_external_members (group_id, first_name, last_name, email, is_active) VALUES (:gid,:first_name,:last_name,:email,:active)");
                foreach ($externalMembers as $ext) {
                    if (!is_array($ext)) { continue; }
                    $email = trim((string)($ext['email'] ?? ''));
                    if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) { continue; }
                    $insExt->execute([':gid'=>$id, ':first_name'=>trim((string)($ext['first_name'] ?? '')), ':last_name'=>trim((string)($ext['last_name'] ?? '')), ':email'=>$email, ':active'=>!empty($ext['is_active']) ? 1 : 1]);
                }
            }
        }
        $pdo->commit();
        api_log('info', 'Mail-Verteiler gespeichert', ['by_user_id' => $currentUser['id'], 'count' => count($seenIds)]);
        $groupsStmt = $pdo->query("SELECT id, name, description, is_active, created_at, updated_at FROM mail_groups ORDER BY name ASC");
        $outGroups = $groupsStmt->fetchAll();
        $membersStmt = $pdo->query("
            SELECT mgm.group_id, u.id AS user_id, u.display_name, u.username, u.email, u.role, u.place, u.is_active
            FROM mail_group_members mgm
            INNER JOIN users u ON u.id = mgm.user_id
            ORDER BY u.display_name ASC, u.username ASC
        ");
        $membersByGroup = [];
        foreach ($membersStmt->fetchAll() as $m) {
            $gid = (int)$m['group_id'];
            if (!isset($membersByGroup[$gid])) { $membersByGroup[$gid] = []; }
            $membersByGroup[$gid][] = $m;
        }
        $externalStmt = $pdo->query("SELECT group_id, id, first_name, last_name, email, is_active FROM mail_group_external_members WHERE is_active=1 ORDER BY last_name ASC, first_name ASC, email ASC");
        $externalByGroup = [];
        foreach ($externalStmt->fetchAll() as $m) {
            $gid = (int)$m['group_id'];
            if (!isset($externalByGroup[$gid])) { $externalByGroup[$gid] = []; }
            $m['member_type'] = 'external';
            $externalByGroup[$gid][] = $m;
        }
        foreach ($outGroups as &$g) {
            $g['members'] = $membersByGroup[(int)$g['id']] ?? [];
            $g['external_members'] = $externalByGroup[(int)$g['id']] ?? [];
        }
        json_response(['success' => true, 'message' => 'Verteiler wurden gespeichert', 'groups' => $outGroups]);
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) { $pdo->rollBack(); }
        api_log('error', 'Mail-Verteiler konnten nicht gespeichert werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Verteiler konnten nicht gespeichert werden'], 500);
    }
}
