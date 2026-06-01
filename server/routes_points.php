<?php
declare(strict_types=1);

if ($method === 'GET' && $path === '/api/point-rules') {
    require_role(['superadmin']);
    $year = (int)($_GET['year'] ?? date('Y'));
    $pdo = db();
    ensure_point_rules_model_columns($pdo);
    $stmt = $pdo->prepare("SELECT id, year, rule_key, label, category, rule_type, source_field, evaluation_source, check_type, min_value, points, is_active, is_system FROM point_rules WHERE year = :year ORDER BY rule_type, category, rule_key");
    $stmt->execute([':year' => $year]);
    json_response(['success' => true, 'year' => $year, 'rules' => $stmt->fetchAll(), 'valid_rules' => valid_point_rules_catalog()]);
}

if ($method === 'PUT' && $path === '/api/point-rules') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $year = (int)($input['year'] ?? date('Y'));
    $rules = $input['rules'] ?? [];
    if (!is_array($rules)) {
        json_response(['success' => false, 'error' => 'rules muss ein Array sein'], 400);
    }
    $pdo = db();
    require_points_year_editable($pdo, $year);
    ensure_point_rules_model_columns($pdo);
    $stmt = $pdo->prepare("\n        INSERT INTO point_rules (year, rule_key, label, category, rule_type, source_field, evaluation_source, check_type, min_value, points, is_active, is_system, updated_by_user_id)\n        VALUES (:year, :rule_key, :label, :category, :rule_type, :source_field, :evaluation_source, :check_type, :min_value, :points, :is_active, :is_system, :updated_by_user_id)\n        ON DUPLICATE KEY UPDATE label = VALUES(label), category = VALUES(category), rule_type = VALUES(rule_type), source_field = VALUES(source_field), evaluation_source = VALUES(evaluation_source), check_type = VALUES(check_type), min_value = VALUES(min_value), points = VALUES(points), is_active = VALUES(is_active), is_system = VALUES(is_system), updated_by_user_id = VALUES(updated_by_user_id)\n    ");
    $keptKeys = [];
    foreach ($rules as $rule) {
        if (!is_array($rule)) {
            continue;
        }
        $key = trim((string)($rule['rule_key'] ?? ''));
        $label = trim((string)($rule['label'] ?? ''));
        if ($key === '' || $label === '') {
            continue;
        }
        $keptKeys[] = $key;
        $stmt->execute([
            ':year' => $year,
            ':rule_key' => $key,
            ':label' => $label,
            ':category' => trim((string)($rule['category'] ?? 'metadata')),
            ':rule_type' => trim((string)($rule['rule_type'] ?? 'metadata')),
            ':source_field' => trim((string)($rule['source_field'] ?? '')),
            ':evaluation_source' => trim((string)($rule['evaluation_source'] ?? '')),
            ':check_type' => trim((string)($rule['check_type'] ?? 'none')),
            ':min_value' => (int)($rule['min_value'] ?? 0),
            ':points' => (int)($rule['points'] ?? 0),
            ':is_active' => !empty($rule['is_active']) ? 1 : 0,
            ':is_system' => !empty($rule['is_system']) ? 1 : 0,
            ':updated_by_user_id' => $currentUser['id'],
        ]);
    }
    if (count($keptKeys) > 0) {
        $placeholders = implode(',', array_fill(0, count($keptKeys), '?'));
        $deleteStmt = $pdo->prepare("DELETE FROM point_rules WHERE year = ? AND rule_key NOT IN ($placeholders)");
        $deleteStmt->execute(array_merge([$year], $keptKeys));
    } else {
        $deleteStmt = $pdo->prepare("DELETE FROM point_rules WHERE year = ?");
        $deleteStmt->execute([$year]);
    }
    api_log('info', 'Punkteregeln gespeichert', ['by_user_id' => $currentUser['id'], 'year' => $year]);
    json_response(['success' => true, 'message' => 'Punkteregeln wurden gespeichert', 'year' => $year]);
}

if ($method === 'GET' && $path === '/api/points/me') {
    $currentUser = current_user();
    $year = (int)($_GET['year'] ?? date('Y'));
    $requestedUserId = (int)($_GET['user_id'] ?? 0);
    if ($requestedUserId > 0 && !is_admin_role($currentUser)) {
        json_response(['success' => false, 'error' => 'Keine Berechtigung für fremde Punktekonten'], 403);
    }
    $pointsUserId = $requestedUserId > 0 ? $requestedUserId : (int)$currentUser['id'];
    $pdo = db();

    $summarySql = "
        SELECT
            cp.user_id,
            cp.user_display_name,
            COALESCE(u.place, '') AS place,
            SUM(CASE WHEN cp.category = 'upload' THEN cp.points ELSE 0 END) AS upload_points,
            SUM(CASE WHEN cp.category = 'metadata' THEN cp.points ELSE 0 END) AS metadata_points,
            SUM(CASE WHEN cp.category = 'persons' THEN cp.points ELSE 0 END) AS persons_points,
            SUM(CASE WHEN cp.category = 'admin_review' THEN cp.points ELSE 0 END) AS admin_points,
            SUM(CASE WHEN cp.is_manual = 1 THEN cp.points ELSE 0 END) AS manual_points,
            SUM(CASE WHEN (d.status = 'uebernommen' OR cp.is_manual = 1) THEN cp.points ELSE 0 END) AS total_points,
            SUM(CASE WHEN (d.status <> 'uebernommen' AND cp.is_manual = 0) THEN cp.points ELSE 0 END) AS provisional_points
        FROM contribution_points cp
        LEFT JOIN users u ON u.id = cp.user_id
        LEFT JOIN documents d ON d.id = cp.document_id
        WHERE cp.points_year = :year
          AND cp.is_confirmed = 1

        GROUP BY cp.user_id, cp.user_display_name, u.place
        ORDER BY total_points DESC, cp.user_display_name ASC
    ";
    $stmt = $pdo->prepare($summarySql);
    $stmt->execute([':year' => $year]);
    $summary = $stmt->fetchAll();

    $rank = null;
    $own = null;
    $position = 0;
    foreach ($summary as $row) {
        $position++;
        if ((int)$row['user_id'] === (int)$pointsUserId) {
            $rank = $position;
            $own = $row;
            break;
        }
    }
    if (!$own) {
        $own = [
            'user_id' => $pointsUserId,
            'user_display_name' => $currentUser['display_name'],
            'place' => $currentUser['place'] ?? '',
            'upload_points' => 0,
            'metadata_points' => 0,
            'persons_points' => 0,
            'admin_points' => 0,
            'manual_points' => 0,
            'total_points' => 0,
            'provisional_points' => 0,
        ];
    }

    $eventsStmt = $pdo->prepare("
        SELECT
            cp.created_at,
            cp.upload_id,
            cp.category,
            cp.rule_key,
            cp.reason,
            cp.points,
            cp.is_manual,
            COALESCE(d.current_filename, d.stored_filename, d.original_filename, cp.upload_id) AS filename,
            COALESCE(d.status, '') AS document_status
        FROM contribution_points cp
        LEFT JOIN documents d ON d.id = cp.document_id
        WHERE cp.user_id = :user_id
          AND cp.points_year = :year
          AND cp.is_confirmed = 1
        ORDER BY cp.created_at DESC, cp.id DESC
        LIMIT 500
    ");
    $eventsStmt->execute([':user_id' => $pointsUserId, ':year' => $year]);

    json_response([
        'success' => true,
        'year' => $year,
        'own' => $own,
        'rank' => $rank,
        'participant_count' => count($summary),
        'events' => $eventsStmt->fetchAll(),
    ]);
}

if ($method === 'GET' && $path === '/api/points/summary') {
    require_role(['admin', 'superadmin']);
    $year = (int)($_GET['year'] ?? date('Y'));
    $pdo = db();
    $stmt = $pdo->prepare("\n        SELECT\n            cp.user_id,\n            cp.user_display_name,\n            COALESCE(u.place, '') AS place,\n            SUM(CASE WHEN cp.category = 'upload' THEN cp.points ELSE 0 END) AS upload_points,\n            SUM(CASE WHEN cp.category = 'metadata' THEN cp.points ELSE 0 END) AS metadata_points,\n            SUM(CASE WHEN cp.category = 'persons' THEN cp.points ELSE 0 END) AS persons_points,\n            SUM(CASE WHEN cp.category = 'admin_review' THEN cp.points ELSE 0 END) AS admin_points,\n            SUM(CASE WHEN cp.is_manual = 1 THEN cp.points ELSE 0 END) AS manual_points,\n            SUM(cp.points) AS total_points\n        FROM contribution_points cp\n        LEFT JOIN users u ON u.id = cp.user_id\n        LEFT JOIN documents d ON d.id = cp.document_id\n        WHERE cp.points_year = :year\n          AND cp.is_confirmed = 1\n          AND (d.status = 'uebernommen' OR cp.is_manual = 1)\n        GROUP BY cp.user_id, cp.user_display_name, u.place\n        ORDER BY total_points DESC, cp.user_display_name ASC\n    ");
    $stmt->execute([':year' => $year]);
    json_response(['success' => true, 'year' => $year, 'summary' => $stmt->fetchAll()]);
}

if ($method === 'GET' && $path === '/api/points/year-status') {
    require_role(['admin', 'superadmin']);
    $year = (int)($_GET['year'] ?? date('Y'));
    $pdo = db();
    ensure_point_year_closures_table($pdo);
    $closure = point_year_closure($pdo, $year);
    $budget = points_year_budget($pdo, $year);
    $totals = points_year_total($pdo, $year);
    $valuePerPoint = ($budget > 0 && $totals['total_points'] > 0) ? round($budget / max(1, $totals['total_points']), 4) : 0.0;
    json_response([
        'success' => true,
        'year' => $year,
        'closed' => $closure !== null,
        'closed_at' => $closure['closed_at'] ?? null,
        'closed_by_user_id' => $closure['closed_by_user_id'] ?? null,
        'closed_by_name' => $closure['closed_by_name'] ?? null,
        'note' => $closure['note'] ?? null,
        'budget' => $budget,
        'total_points' => $totals['total_points'],
        'participant_count' => $totals['participant_count'],
        'value_per_point' => $valuePerPoint,
    ]);
}

if ($method === 'PUT' && $path === '/api/points/year-budget') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $year = (int)($input['year'] ?? date('Y'));
    $budgetRaw = $input['budget'] ?? null;
    if ($budgetRaw === null || $budgetRaw === '') {
        json_response(['success' => false, 'error' => 'Bitte einen Prämienbetrag angeben'], 400);
    }
    $budget = (float)str_replace(',', '.', (string)$budgetRaw);
    if ($budget < 0) {
        json_response(['success' => false, 'error' => 'Der Prämienbetrag darf nicht negativ sein'], 400);
    }
    $pdo = db();
    require_points_year_editable($pdo, $year);
    setting_set($pdo, points_year_budget_key($year), (string)$budget);
    api_log('info', 'Punktebudget gespeichert', ['by_user_id' => $currentUser['id'] ?? null, 'year' => $year, 'budget' => $budget]);
    json_response(['success' => true, 'year' => $year, 'budget' => $budget]);
}

if ($method === 'POST' && $path === '/api/points/year-close') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $year = (int)($input['year'] ?? date('Y'));
    $note = trim((string)($input['note'] ?? ''));
    $pdo = db();
    ensure_point_year_closures_table($pdo);
    $stmt = $pdo->prepare("\n        INSERT INTO point_year_closures (year, closed_at, closed_by_user_id, note)\n        VALUES (:year, NOW(), :closed_by_user_id, :note)\n        ON DUPLICATE KEY UPDATE closed_at = VALUES(closed_at), closed_by_user_id = VALUES(closed_by_user_id), note = VALUES(note)\n    ");
    $stmt->execute([
        ':year' => $year,
        ':closed_by_user_id' => (int)$currentUser['id'],
        ':note' => $note !== '' ? $note : null,
    ]);
    api_log('info', 'Punktejahr abgeschlossen', ['by_user_id' => $currentUser['id'] ?? null, 'year' => $year]);
    json_response(['success' => true, 'year' => $year, 'closed' => true]);
}

if ($method === 'POST' && $path === '/api/points/year-reopen') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $year = (int)($input['year'] ?? date('Y'));
    $pdo = db();
    ensure_point_year_closures_table($pdo);
    $stmt = $pdo->prepare("DELETE FROM point_year_closures WHERE year = :year");
    $stmt->execute([':year' => $year]);
    api_log('info', 'Punktejahr wieder geöffnet', ['by_user_id' => $currentUser['id'] ?? null, 'year' => $year]);
    json_response(['success' => true, 'year' => $year, 'closed' => false]);
}

if ($method === 'GET' && preg_match('#^/api/documents/([^/]+)/points$#', $path, $matches)) {
    require_role(['admin', 'superadmin']);
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM contribution_points WHERE upload_id = :upload_id ORDER BY created_at ASC, id ASC");
    $stmt->execute([':upload_id' => $uploadId]);
    json_response(['success' => true, 'upload_id' => $uploadId, 'points' => $stmt->fetchAll()]);
}

if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/manual-points$#', $path, $matches)) {
    $currentUser = require_role(['admin', 'superadmin']);
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $targetUserId = (int)($input['user_id'] ?? 0);
    $points = (int)($input['points'] ?? 0);
    $reason = trim((string)($input['reason'] ?? ''));
    $category = trim((string)($input['category'] ?? 'manual_bonus')) ?: 'manual_bonus';
    $ruleKey = trim((string)($input['rule_key'] ?? ''));
    if ($ruleKey === '') {
        $ruleKey = 'manual_bonus_' . time();
    }
    $sourceField = trim((string)($input['source_field'] ?? ''));
    if ($sourceField === '') {
        $sourceField = point_rule_source_field_from_key($ruleKey);
    }
    if ($targetUserId <= 0 || $points === 0 || $reason === '') {
        json_response(['success' => false, 'error' => 'Benutzer, Punkte und Begründung sind erforderlich'], 400);
    }
    $pdo = db();
    $docStmt = $pdo->prepare("SELECT id, upload_id FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $docStmt->execute([':upload_id' => $uploadId]);
    $doc = $docStmt->fetch();
    if (!$doc) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    require_points_year_editable($pdo, current_points_year());
    $userStmt = $pdo->prepare("SELECT id, display_name FROM users WHERE id = :id LIMIT 1");
    $userStmt->execute([':id' => $targetUserId]);
    $beneficiary = $userStmt->fetch();
    if (!$beneficiary) {
        json_response(['success' => false, 'error' => 'Benutzer nicht gefunden'], 404);
    }
    add_contribution_point($pdo, (int)$doc['id'], $uploadId, ['id' => (int)$beneficiary['id'], 'display_name' => $beneficiary['display_name']], $currentUser, $category, $ruleKey, $reason, $sourceField, $points, true);
    $hist = $pdo->prepare("INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, new_value) VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :new_value)");
    $hist->execute([':document_id' => (int)$doc['id'], ':upload_id' => $uploadId, ':user_id' => $currentUser['id'], ':user_display_name' => $currentUser['display_name'], ':action' => 'manual_points_added', ':details' => $reason, ':new_value' => (string)$points]);
    json_response(['success' => true, 'message' => 'Sonderpunkte wurden gespeichert']);
}

if ($method === 'GET' && $path === '/api/admin/manual-points-settings') {
    require_role(['admin', 'superadmin']);
    $pdo = db();
    $pointsPerHour = (int)setting_get($pdo, 'manual_points_per_hour', '150');
    json_response(['success' => true, 'points_per_hour' => $pointsPerHour]);
}

if ($method === 'PUT' && $path === '/api/admin/manual-points-settings') {
    require_role(['superadmin']);
    $input = get_json_input();
    $pointsPerHour = (int)($input['points_per_hour'] ?? 150);
    if ($pointsPerHour <= 0) {
        json_response(['success' => false, 'error' => 'Punkte pro Stunde müssen größer als 0 sein'], 400);
    }
    $pdo = db();
    setting_set($pdo, 'manual_points_per_hour', (string)$pointsPerHour);
    json_response(['success' => true, 'points_per_hour' => $pointsPerHour]);
}

if ($method === 'GET' && $path === '/api/manual-points') {
    $currentUser = require_role(['admin', 'superadmin', 'ortschronist']);
    $pdo = db();
    ensure_manual_special_points_table($pdo);
    $year = isset($_GET['year']) ? (int)$_GET['year'] : (int)date('Y');
    $where = 'msp.points_year = :year';
    $params = [':year' => $year];
    if (($currentUser['role'] ?? '') === 'ortschronist') {
        $where .= ' AND msp.user_id = :uid';
        $params[':uid'] = (int)$currentUser['id'];
    }
    $stmt = $pdo->prepare("SELECT msp.*, COALESCE(u.place, '') AS place FROM manual_special_points msp LEFT JOIN users u ON u.id = msp.user_id WHERE $where ORDER BY msp.activity_date DESC, msp.created_at DESC, msp.id DESC");
    $stmt->execute($params);
    json_response(['success' => true, 'year' => $year, 'items' => $stmt->fetchAll()]);
}

if ($method === 'POST' && $path === '/api/manual-points') {
    $currentUser = require_role(['admin', 'superadmin']);
    $pdo = db();
    ensure_manual_special_points_table($pdo);
    require_points_year_editable($pdo, (int)date('Y'));
    $input = get_json_input();
    $targetUserId = (int)($input['user_id'] ?? 0);
    $ruleKey = trim((string)($input['rule_key'] ?? 'manual_other'));
    $points = (int)($input['points'] ?? 0);
    $reason = trim((string)($input['reason'] ?? ''));
    $note = trim((string)($input['note'] ?? ''));
    $activityDate = trim((string)($input['activity_date'] ?? ''));
    $hoursRaw = $input['hours'] ?? null;
    $hours = ($hoursRaw === null || $hoursRaw === '') ? null : (float)str_replace(',', '.', (string)$hoursRaw);
    if ($targetUserId <= 0 || $points === 0 || $reason === '') {
        json_response(['success' => false, 'error' => 'Benutzer, Punkte und Begründung sind erforderlich'], 400);
    }
    if ($activityDate === '') {
        $activityDate = date('Y-m-d');
    }
    $userStmt = $pdo->prepare("SELECT id, display_name FROM users WHERE id = :id AND is_active = 1 LIMIT 1");
    $userStmt->execute([':id' => $targetUserId]);
    $beneficiary = $userStmt->fetch();
    if (!$beneficiary) {
        json_response(['success' => false, 'error' => 'Benutzer nicht gefunden oder nicht aktiv'], 404);
    }
    $ruleLabel = $ruleKey;
    $ruleStmt = $pdo->prepare("SELECT label FROM point_rules WHERE rule_key = :rule_key AND year = :year LIMIT 1");
    $year = (int)substr($activityDate, 0, 4);
    if ($year <= 0) { $year = (int)date('Y'); }
    $ruleStmt->execute([':rule_key' => $ruleKey, ':year' => $year]);
    $label = $ruleStmt->fetchColumn();
    if ($label !== false) { $ruleLabel = (string)$label; }
    $stmt = $pdo->prepare("INSERT INTO manual_special_points (user_id, user_display_name, points_year, activity_date, rule_key, rule_label, hours, points, reason, note, created_by_user_id, created_by_name) VALUES (:user_id, :user_display_name, :points_year, :activity_date, :rule_key, :rule_label, :hours, :points, :reason, :note, :created_by_user_id, :created_by_name)");
    $stmt->execute([
        ':user_id' => (int)$beneficiary['id'],
        ':user_display_name' => (string)$beneficiary['display_name'],
        ':points_year' => $year,
        ':activity_date' => $activityDate,
        ':rule_key' => $ruleKey,
        ':rule_label' => $ruleLabel,
        ':hours' => $hours,
        ':points' => $points,
        ':reason' => $reason,
        ':note' => $note,
        ':created_by_user_id' => (int)$currentUser['id'],
        ':created_by_name' => (string)$currentUser['display_name'],
    ]);
    json_response(['success' => true, 'message' => 'Manuelle Sonderpunkte wurden gespeichert']);
}

if ($method === 'POST' && $path === '/api/points/recalculate-bulk') {
    $currentUser = require_role(['superadmin']);
    try {
        $input = get_json_input();
        $uploadIds = $input['upload_ids'] ?? [];
        if (!is_array($uploadIds) || count($uploadIds) === 0) {
            json_response(['success' => false, 'error' => 'Keine Upload-IDs übergeben'], 400);
        }
        $uploadIds = array_values(array_unique(array_filter(array_map('strval', $uploadIds))));
        if (count($uploadIds) > 500) {
            json_response(['success' => false, 'error' => 'Maximal 500 Dateien pro Lauf erlaubt'], 400);
        }
        $pdo = db();
        require_points_year_editable($pdo, current_points_year());
        ensure_points_schema_available($pdo);
        $stats = ['processed' => 0, 'eligible' => 0, 'created' => 0, 'existing' => 0, 'skipped_existing' => 0, 'skipped_ineligible' => 0, 'skipped_no_user' => 0, 'skipped_zero' => 0, 'skipped_closed' => 0, 'not_found' => 0];
        $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
        foreach ($uploadIds as $uploadId) {
            $stmt->execute([':upload_id' => $uploadId]);
            $doc = $stmt->fetch();
            if (!$doc) { $stats['not_found']++; continue; }
            $stats['processed']++;
            if (is_point_eligible_document($doc)) { $stats['eligible']++; }
            $docStats = recalculate_points_for_document($pdo, $doc, $currentUser);
            $stats = merge_point_stats($stats, $docStats);
        }
        $stats['skipped_existing'] = $stats['existing'] ?? 0;
        api_log('info', 'Punkte-Nachberechnung abgeschlossen', ['by_user_id' => $currentUser['id'] ?? null, 'processed' => $stats['processed'], 'created' => $stats['created'], 'existing' => $stats['existing'], 'skipped_ineligible' => $stats['skipped_ineligible']]);
        json_response(array_merge(['success' => true, 'message' => 'Punkte wurden für die angezeigte Liste nachberechnet'], $stats));
    } catch (Throwable $e) {
        api_log('error', 'Punkte-Nachberechnung fehlgeschlagen', ['by_user_id' => $currentUser['id'] ?? null, 'error' => $e->getMessage(), 'file' => $e->getFile(), 'line' => $e->getLine()]);
        json_response(['success' => false, 'error' => 'Punkte-Nachberechnung fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}

if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/points/recalculate$#', $path, $matches)) {
    $currentUser = require_role(['admin', 'superadmin']);
    try {
        $uploadId = urldecode($matches[1]);
        $pdo = db();
        require_points_year_editable($pdo, current_points_year());
        ensure_points_schema_available($pdo);
        $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
        $stmt->execute([':upload_id' => $uploadId]);
        $doc = $stmt->fetch();
        if (!$doc) {
            json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
        }
        $stats = recalculate_points_for_document($pdo, $doc, $currentUser);
        json_response(array_merge(['success' => true, 'message' => 'Punkte wurden neu berechnet'], $stats));
    } catch (Throwable $e) {
        api_log('error', 'Punkte-Nachberechnung für Dokument fehlgeschlagen', ['by_user_id' => $currentUser['id'] ?? null, 'upload_id' => $matches[1] ?? null, 'error' => $e->getMessage(), 'file' => $e->getFile(), 'line' => $e->getLine()]);
        json_response(['success' => false, 'error' => 'Punkte-Nachberechnung fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}
