<?php

declare(strict_types=1);

require_once __DIR__ . '/routes_shared_points_permissions.php';
require_once __DIR__ . '/routes_shared_points_year.php';
require_once __DIR__ . '/routes_shared_points_rules.php';
require_once __DIR__ . '/routes_shared_points_paths.php';
require_once __DIR__ . '/routes_shared_db_utils.php';

function is_point_eligible_document(array $document): bool
{
    if (array_key_exists('points_eligible', $document) && $document['points_eligible'] !== null && $document['points_eligible'] !== '') {
        return ((int)$document['points_eligible']) === 1;
    }
    return is_point_eligible_path((string)($document['target_folder'] ?? '')) || is_point_eligible_path((string)($document['current_path'] ?? ''));
}

function document_context_for_points(PDO $pdo, int $documentId): ?array
{
    $hasPointsEligible = db_column_exists($pdo, 'documents', 'points_eligible');
    $sql = $hasPointsEligible
        ? "SELECT id, original_filename, stored_filename, current_filename, document_type, target_folder, current_path, points_eligible FROM documents WHERE id = :id LIMIT 1"
        : "SELECT id, original_filename, stored_filename, current_filename, document_type, target_folder, current_path, 0 AS points_eligible FROM documents WHERE id = :id LIMIT 1";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([':id' => $documentId]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function is_image_document_context(array $document): bool
{
    $type = strtolower((string)($document['document_type'] ?? ''));
    if (str_contains($type, 'bild') || str_contains($type, 'foto') || str_contains($type, 'photo') || str_contains($type, 'image')) {
        return true;
    }
    $name = strtolower((string)($document['current_filename'] ?? $document['stored_filename'] ?? $document['original_filename'] ?? $document['current_path'] ?? ''));
    return (bool)preg_match('/\.(jpe?g|png|gif|bmp|tiff?|webp)$/i', $name);
}

function points_description_is_eligible(string $text): bool
{
    $text = trim($text);
    if (function_exists('mb_strlen')) {
        return mb_strlen($text, 'UTF-8') >= 50;
    }
    return strlen($text) >= 50;
}

function points_keyword_count(string $text): int
{
    $parts = preg_split('/[;,]+/u', $text);
    $count = 0;
    if (is_array($parts)) {
        foreach ($parts as $part) {
            if (trim((string)$part) !== '') {
                $count++;
            }
        }
    }
    return $count;
}

function points_value_matches_rule(string $field, string $value, string $checkType, int $minValue): bool
{
    $value = trim($value);
    if ($value === '') {
        return false;
    }
    if ($checkType === 'none') {
        return true;
    }
    if ($checkType === 'words') {
        $words = preg_split('/\s+/u', $value, -1, PREG_SPLIT_NO_EMPTY);
        return count($words ?: []) >= max(1, $minValue);
    }
    if ($checkType === 'count') {
        return points_keyword_count($value) >= max(1, $minValue);
    }
    $length = function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
    return $length >= max(1, $minValue);
}

function points_metadata_field_is_eligible(PDO $pdo, int $year, string $field, string $source, string $value): bool
{
    $catalog = metadata_point_rule_catalog();
    $default = $catalog[$field] ?? ['check_type' => 'characters', 'min_value' => 1];
    $rule = point_rule_config($pdo, $year, metadata_point_rule_key($field, $source));
    if (!$rule) {
        return false;
    }
    return points_value_matches_rule(
        $field,
        $value,
        (string)($rule['check_type'] ?? $default['check_type']),
        (int)($rule['min_value'] ?? $default['min_value'])
    );
}

function add_contribution_point(PDO $pdo, int $documentId, string $uploadId, array $beneficiary, array $createdBy, string $category, string $ruleKey, string $reason, string $sourceField, int $points, bool $manual = false): void
{
    if ($points <= 0) {
        return;
    }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_point_eligible_document($documentContext)) {
        return;
    }
    $year = (int)date('Y');
    if (point_year_is_closed($pdo, $year)) {
        api_log('warning', 'Punktevergabe blockiert, Jahr ist abgeschlossen', ['document_id' => $documentId, 'upload_id' => $uploadId, 'rule_key' => $ruleKey, 'year' => $year]);
        return;
    }
    try {
        $stmt = $pdo->prepare("
            INSERT INTO contribution_points (document_id, upload_id, user_id, user_display_name, points_year, category, rule_key, reason, source_field, points, created_by_user_id, created_by_name, is_manual, is_confirmed)
            VALUES (:document_id, :upload_id, :user_id, :user_display_name, :points_year, :category, :rule_key, :reason, :source_field, :points, :created_by_user_id, :created_by_name, :is_manual, 1)
        ");
        $stmt->execute([
            ':document_id' => $documentId,
            ':upload_id' => $uploadId,
            ':user_id' => (int)$beneficiary['id'],
            ':user_display_name' => (string)$beneficiary['display_name'],
            ':points_year' => $year,
            ':category' => $category,
            ':rule_key' => $ruleKey,
            ':reason' => $reason,
            ':source_field' => $sourceField,
            ':points' => $points,
            ':created_by_user_id' => (int)$createdBy['id'],
            ':created_by_name' => (string)$createdBy['display_name'],
            ':is_manual' => $manual ? 1 : 0,
        ]);
    } catch (PDOException $e) {
        // Dubletten sind durch den Unique-Key möglich und sollen keine Bearbeitung blockieren.
        if ((int)$e->getCode() !== 23000) {
            throw $e;
        }
    }
}

function text_change_size(string $old, string $new): int
{
    $old = trim($old);
    $new = trim($new);
    if ($old === $new) { return 0; }
    $oldLen = function_exists('mb_strlen') ? mb_strlen($old, 'UTF-8') : strlen($old);
    $newLen = function_exists('mb_strlen') ? mb_strlen($new, 'UTF-8') : strlen($new);
    return max(abs($newLen - $oldLen), levenshtein(substr($old, 0, 255), substr($new, 0, 255)));
}

function remove_own_auto_points_for_field(PDO $pdo, int $documentId, int $userId, string $ruleKey, string $sourceField): void
{
    if ($userId <= 0) { return; }
    $stmt = $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND user_id = :user_id AND rule_key = :rule_key AND source_field = :source_field AND is_manual = 0");
    $stmt->execute([':document_id' => $documentId, ':user_id' => $userId, ':rule_key' => $ruleKey, ':source_field' => $sourceField]);
}

function remove_auto_points_for_field(PDO $pdo, int $documentId, string $ruleKey, string $sourceField): void
{
    $stmt = $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND rule_key = :rule_key AND source_field = :source_field AND is_manual = 0");
    $stmt->execute([':document_id' => $documentId, ':rule_key' => $ruleKey, ':source_field' => $sourceField]);
}

function add_correction_point_if_relevant(PDO $pdo, int $documentId, string $uploadId, array $user, string $field, string $old, string $new): void
{
    $delta = text_change_size($old, $new);
    if ($delta <= 30) { return; }
    $year = current_points_year();
    $ruleKey = 'metadata_correction_' . $field;
    $sourceField = $field . '_correction';
    if (point_exists_for_document_rule($pdo, $documentId, $ruleKey, $sourceField, false)) { return; }
    $points = point_rule_points($pdo, $year, 'metadata_correction', 1);
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $ruleKey, 'Fachliche Korrektur/Ergänzung: ' . $field, $sourceField, $points, false);
}

function add_auto_points_for_metadata(PDO $pdo, int $documentId, string $uploadId, array $user, array $values, ?array $oldValues = null, array $openaiFields = []): void
{
    $year = current_points_year();
    $openaiFields = array_values(array_unique(array_filter(array_map(static fn($field) => trim((string)$field), $openaiFields))));
    $openaiFieldSet = array_fill_keys($openaiFields, true);
    $rules = metadata_point_rule_catalog();
    foreach ($rules as $field => $info) {
        $new = trim((string)($values[$field] ?? ''));
        $old = $oldValues === null ? '' : trim((string)($oldValues[$field] ?? ''));
        $openAiRuleKey = metadata_point_rule_key($field, 'openAI');
        $manualRuleKey = metadata_point_rule_key($field, 'manual');
        $newOpenAiEligible = isset($openaiFieldSet[$field]) && $old === '' && points_metadata_field_is_eligible($pdo, $year, $field, 'openAI', $new);
        $newManualEligible = !$newOpenAiEligible && points_metadata_field_is_eligible($pdo, $year, $field, 'manual', $new);
        if ($newOpenAiEligible) {
            $points = point_rule_points($pdo, $year, $openAiRuleKey, 1);
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $openAiRuleKey, $info['label'], $field, $points, false);
        } elseif ($newManualEligible) {
            remove_auto_points_for_field($pdo, $documentId, $openAiRuleKey, $field);
            $points = point_rule_points($pdo, $year, $manualRuleKey, 2);
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $manualRuleKey, $info['label'], $field, $points, false);
        } else {
            remove_auto_points_for_field($pdo, $documentId, $openAiRuleKey, $field);
            remove_auto_points_for_field($pdo, $documentId, $manualRuleKey, $field);
        }
    }
    $transDone = (bool)($values['transcription_done'] ?? false);
    $oldTransDone = $oldValues === null ? false : (bool)($oldValues['transcription_done'] ?? false);
    if ($transDone && !$oldTransDone) {
        $type = strtolower(trim((string)($values['transcription_type'] ?? '')));
        $rule = 'transcription_short'; $default = 3; $label = 'Transkription / Abschrift erstellt';
        if (str_contains($type, 'schwierig') || str_contains($type, 'handschrift')) { $rule = 'transcription_difficult'; $default = 8; $label = 'Schwierige Transkription'; }
        elseif (str_contains($type, 'zeitung') || str_contains($type, 'akte') || str_contains($type, 'urkunde')) { $rule = 'transcription_document'; $default = 10; $label = 'Transkription Zeitung / Akte / Urkunde'; }
        elseif (str_contains($type, 'voll')) { $rule = 'transcription_full'; $default = 5; $label = 'Vollständige Transkription'; }
        $points = point_rule_points($pdo, $year, $rule, $default);
        add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'metadata', $rule, $label, 'transcription_done', $points, false);
    }
}

function add_person_points(PDO $pdo, int $documentId, string $uploadId, array $user, array $persons): void
{
    $pdo->prepare("DELETE FROM contribution_points WHERE document_id = :document_id AND category = 'persons' AND is_manual = 0")->execute([':document_id' => $documentId]);
    if (count($persons) <= 0) {
        return;
    }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_image_document_context($documentContext)) {
        return;
    }
    $year = current_points_year();
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'persons', 'persons_image_marked', 'Bild mit Personenmarkierungen', 'persons_image', point_rule_points($pdo, $year, 'persons_image_marked', 5), false);
    $index = 0;
    foreach ($persons as $person) {
        if (is_array($person)) {
            $index++;
            $number = (int)($person['number'] ?? $index);
            if ($number <= 0) { $number = $index; }
            add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'persons', 'persons_per_person', 'Personenmarkierung je Person', 'person_' . $number, point_rule_points($pdo, $year, 'persons_per_person', 1), false);
        }
    }
}

function point_user_array(int $id, string $displayName): array
{
    return ['id' => $id, 'display_name' => $displayName !== '' ? $displayName : ('Benutzer ' . $id)];
}

function document_uploader_for_points(array $doc): array
{
    return point_user_array((int)($doc['uploaded_by_user_id'] ?? 0), (string)($doc['uploaded_by_name'] ?? $doc['uploaded_by_display_name'] ?? ''));
}

function point_exists_for_document_rule(PDO $pdo, int $documentId, string $ruleKey, string $sourceField, bool $manual = false): bool
{
    $stmt = $pdo->prepare("SELECT id FROM contribution_points WHERE document_id = :document_id AND rule_key = :rule_key AND COALESCE(source_field, '') = :source_field AND is_manual = :is_manual LIMIT 1");
    $stmt->execute([
        ':document_id' => $documentId,
        ':rule_key' => $ruleKey,
        ':source_field' => $sourceField,
        ':is_manual' => $manual ? 1 : 0,
    ]);
    return (bool)$stmt->fetch();
}

function add_contribution_point_retro(PDO $pdo, int $documentId, string $uploadId, array $beneficiary, array $createdBy, string $category, string $ruleKey, string $reason, string $sourceField, int $points): string
{
    if ($points <= 0) { return 'skipped_zero'; }
    if ((int)($beneficiary['id'] ?? 0) <= 0) { return 'skipped_no_user'; }
    $documentContext = document_context_for_points($pdo, $documentId);
    if (!$documentContext || !is_point_eligible_document($documentContext)) { return 'skipped_ineligible'; }
    if (point_year_is_closed($pdo, current_points_year())) { return 'skipped_closed'; }
    if (point_exists_for_document_rule($pdo, $documentId, $ruleKey, $sourceField, false)) { return 'existing'; }
    add_contribution_point($pdo, $documentId, $uploadId, $beneficiary, $createdBy, $category, $ruleKey, $reason, $sourceField, $points, false);
    return 'created';
}

function metadata_field_beneficiary(PDO $pdo, array $doc, string $field): array
{
    try {
        $stmt = $pdo->prepare("
            SELECT user_id, user_display_name
            FROM document_history
            WHERE document_id = :document_id
              AND action = 'document_updated'
              AND details = :details
              AND (old_value IS NULL OR old_value = '')
              AND new_value IS NOT NULL AND new_value <> ''
              AND user_id IS NOT NULL AND user_id > 0
            ORDER BY created_at ASC, id ASC
            LIMIT 1
        ");
        $stmt->execute([':document_id' => (int)$doc['id'], ':details' => 'Feld geändert: ' . $field]);
        $row = $stmt->fetch();
        if ($row) {
            return point_user_array((int)$row['user_id'], (string)$row['user_display_name']);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Punkte-Nachberechnung: Feld-Historie konnte nicht ausgewertet werden', ['document_id' => $doc['id'] ?? null, 'field' => $field, 'error' => $e->getMessage()]);
    }
    return document_uploader_for_points($doc);
}

function admin_review_beneficiary(PDO $pdo, array $doc, string $field, string $newValue): ?array
{
    try {
        $stmt = $pdo->prepare("
            SELECT user_id, user_display_name
            FROM document_history
            WHERE document_id = :document_id
              AND action = 'document_updated'
              AND details = :details
              AND new_value = :new_value
              AND user_id IS NOT NULL AND user_id > 0
            ORDER BY created_at ASC, id ASC
            LIMIT 1
        ");
        $stmt->execute([':document_id' => (int)$doc['id'], ':details' => 'Feld geändert: ' . $field, ':new_value' => $newValue]);
        $row = $stmt->fetch();
        if ($row) {
            return point_user_array((int)$row['user_id'], (string)$row['user_display_name']);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Punkte-Nachberechnung: Admin-Historie konnte nicht ausgewertet werden', ['document_id' => $doc['id'] ?? null, 'field' => $field, 'error' => $e->getMessage()]);
    }
    return null;
}

function recalculate_points_for_document(PDO $pdo, array $doc, array $currentUser): array
{
    $stats = ['created' => 0, 'existing' => 0, 'skipped_ineligible' => 0, 'skipped_no_user' => 0, 'skipped_zero' => 0, 'skipped_closed' => 0];
    $documentId = (int)$doc['id'];
    $uploadId = (string)$doc['upload_id'];
    if (!is_point_eligible_document($doc)) {
        $stats['skipped_ineligible']++;
        return $stats;
    }
    $year = current_points_year();
    $rules = metadata_point_rule_catalog();
    foreach ($rules as $field => $info) {
        if (!points_metadata_field_is_eligible($pdo, $year, $field, 'manual', (string)($doc[$field] ?? ''))) { continue; }
        $beneficiary = metadata_field_beneficiary($pdo, $doc, $field);
        $ruleKey = metadata_point_rule_key($field, 'manual');
        $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'metadata', $ruleKey, $info['label'], $field, point_rule_points($pdo, $year, $ruleKey, 2));
        $stats[$result] = ($stats[$result] ?? 0) + 1;
    }
    if ((int)($doc['transcription_done'] ?? 0) === 1) {
        $type = strtolower(trim((string)($doc['transcription_type'] ?? '')));
        $rule = 'transcription_short'; $default = 3; $label = 'Transkription / Abschrift erstellt';
        if (str_contains($type, 'schwierig') || str_contains($type, 'handschrift')) { $rule = 'transcription_difficult'; $default = 8; $label = 'Schwierige Transkription'; }
        elseif (str_contains($type, 'zeitung') || str_contains($type, 'akte') || str_contains($type, 'urkunde')) { $rule = 'transcription_document'; $default = 10; $label = 'Transkription Zeitung / Akte / Urkunde'; }
        elseif (str_contains($type, 'voll')) { $rule = 'transcription_full'; $default = 5; $label = 'Vollständige Transkription'; }
        $beneficiary = metadata_field_beneficiary($pdo, $doc, 'transcription_done');
        $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'metadata', $rule, $label, 'transcription_done', point_rule_points($pdo, $year, $rule, $default));
        $stats[$result] = ($stats[$result] ?? 0) + 1;
    }
    $persons = [];
    if (db_table_exists($pdo, 'document_persons')) {
        try {
            $personColumns = "number, display_name";
            $personColumns .= db_column_exists($pdo, 'document_persons', 'created_by_user_id') ? ", created_by_user_id" : ", NULL AS created_by_user_id";
            $personColumns .= db_column_exists($pdo, 'document_persons', 'created_by_name') ? ", created_by_name" : ", NULL AS created_by_name";
            $pstmt = $pdo->prepare("SELECT " . $personColumns . " FROM document_persons WHERE document_id = :document_id");
            $pstmt->execute([':document_id' => $documentId]);
            $persons = $pstmt->fetchAll();
        } catch (Throwable $e) {
            api_log('warning', 'Punkte-Nachberechnung: Personen konnten nicht ausgewertet werden', ['document_id' => $documentId, 'error' => $e->getMessage()]);
            $persons = [];
        }
    }
    if (count($persons) > 0) {
        $personBeneficiary = null;
        foreach ($persons as $p) {
            if ((int)($p['created_by_user_id'] ?? 0) > 0) { $personBeneficiary = point_user_array((int)$p['created_by_user_id'], (string)($p['created_by_name'] ?? '')); break; }
        }
        if (!$personBeneficiary) { $personBeneficiary = document_uploader_for_points($doc); }
        if (is_image_document_context($doc)) {
            $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $personBeneficiary, $currentUser, 'persons', 'persons_image_marked', 'Bild mit Personenmarkierungen', 'persons_image', point_rule_points($pdo, $year, 'persons_image_marked', 5));
            $stats[$result] = ($stats[$result] ?? 0) + 1;
            $index = 0;
            foreach ($persons as $p) {
                $index++;
                $number = (int)($p['number'] ?? $index);
                if ($number <= 0) { $number = $index; }
                $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $personBeneficiary, $currentUser, 'persons', 'persons_per_person', 'Personenmarkierung je Person', 'person_' . $number, point_rule_points($pdo, $year, 'persons_per_person', 1));
                $stats[$result] = ($stats[$result] ?? 0) + 1;
            }
        }
    }
    if ((string)($doc['status'] ?? '') === 'erfasst') {
        $beneficiary = admin_review_beneficiary($pdo, $doc, 'status', 'erfasst');
        if ($beneficiary) {
            $result = add_contribution_point_retro($pdo, $documentId, $uploadId, $beneficiary, $currentUser, 'admin_review', 'admin_review_accepted', 'Dokument erfasst', 'status', point_rule_points($pdo, $year, 'admin_review_accepted', 1));
            $stats[$result] = ($stats[$result] ?? 0) + 1;
        }
    }
    return $stats;
}

function merge_point_stats(array $base, array $add): array
{
    foreach ($add as $key => $value) {
        $base[$key] = ($base[$key] ?? 0) + (int)$value;
    }
    return $base;
}

function add_special_collection_points(PDO $pdo, int $documentId, string $uploadId, array $user, string $targetFolder, string $currentPath, string $captureMode): void
{
    $collection = special_collection_for_document_path($targetFolder, $currentPath);
    if ($collection === null) {
        return;
    }
    $isExistingMetadata = ($captureMode === 'existing_file_metadata');
    $year = current_points_year();
    $points = point_rule_points($pdo, $year, 'special_collection', 10);
    $ruleKey = 'special_collection';
    if ($collection === 'kinder_wie_die_zeit_vergeht') {
        $reason = $isExistingMetadata ? 'Kinder wie die Zeit vergeht: nachträgliche Metadatenerfassung' : 'Kinder wie die Zeit vergeht: neu über ODV abgelegt';
    } else {
        $reason = $isExistingMetadata ? 'Jahresblätter: nachträgliche Metadatenerfassung' : 'Jahresblätter: neu über ODV abgelegt';
    }
    add_contribution_point($pdo, $documentId, $uploadId, $user, $user, 'special_collection', $ruleKey, $reason, 'current_path', $points, false);
}
