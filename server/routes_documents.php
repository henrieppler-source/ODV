<?php
declare(strict_types=1);

if ($method === 'POST' && $path === '/api/documents') {
    $currentUser = current_user();
    $input = get_json_input();

    $uploadId = trim((string)($input['upload_id'] ?? ''));
    $originalFilename = trim((string)($input['original_filename'] ?? ''));
    $storedFilename = trim((string)($input['stored_filename'] ?? $originalFilename));
    $currentFilename = trim((string)($input['current_filename'] ?? $storedFilename));
    $targetFolder = trim((string)($input['target_folder'] ?? ''));
    $currentPath = trim((string)($input['current_path'] ?? ''));
    $uploadedAt = trim((string)($input['uploaded_at'] ?? date('Y-m-d H:i:s')));
    $status = validate_document_status(trim((string)($input['status'] ?? 'hochgeladen')));
    $metadata = is_array($input['metadata'] ?? null) ? $input['metadata'] : [];
    $captureMode = trim((string)($input['odv_capture_mode'] ?? 'odv_upload'));

    if ($uploadId === '' || $originalFilename === '') {
        json_response(['success' => false, 'error' => 'upload_id und original_filename sind erforderlich'], 400);
    }

    $pdo = db();
    $uploadOwner = $currentUser;
    $requestedOwnerId = (int)($input['import_uploaded_by_user_id'] ?? $input['uploaded_by_user_id'] ?? 0);
    if ($requestedOwnerId > 0) {
        if ($requestedOwnerId !== (int)($currentUser['id'] ?? 0) && !is_admin_role($currentUser)) {
            json_response(['success' => false, 'error' => 'Nur Admins dürfen beim Erfassen einen anderen Benutzer zuordnen'], 403);
        }
        $ownerStmt = $pdo->prepare("SELECT id, username, display_name, email, role, place, is_active FROM users WHERE id = :id LIMIT 1");
        $ownerStmt->execute([':id' => $requestedOwnerId]);
        $owner = $ownerStmt->fetch();
        if (!$owner || (int)($owner['is_active'] ?? 0) !== 1) {
            json_response(['success' => false, 'error' => 'Gewählter Benutzer für Import nicht gefunden oder deaktiviert'], 400);
        }
        $uploadOwner = [
            'id' => (int)$owner['id'],
            'username' => $owner['username'],
            'display_name' => $owner['display_name'],
            'email' => $owner['email'] ?? null,
            'role' => $owner['role'],
            'place' => $owner['place'],
        ];
    }

    $permissionDoc = [
        'target_folder' => $targetFolder,
        'current_path' => $currentPath,
        'uploaded_by_user_id' => $currentUser['id'],
    ];
    ensure_document_write_permission($pdo, $currentUser, $permissionDoc);

    try {
        $pdo->beginTransaction();
        $stmt = $pdo->prepare("\n            INSERT INTO documents (\n                upload_id, original_filename, stored_filename, current_filename, target_folder, current_path,\n                uploaded_by_user_id, uploaded_by_name, uploaded_at, status, points_eligible,\n                document_type, source, original_location, document_date, event, place, description, note,\n                copyright_author, rights_holder, usage_permission, license_note, rights_note,\n                archive_name, archive_signature, archive_accessed_at, keywords, transcription_done, transcription_type, transcription_note, person_status, json_metadata\n            ) VALUES (\n                :upload_id, :original_filename, :stored_filename, :current_filename, :target_folder, :current_path,\n                :uploaded_by_user_id, :uploaded_by_name, :uploaded_at, :status, :points_eligible,\n                :document_type, :source, :original_location, :document_date, :event, :place, :description, :note,\n                :copyright_author, :rights_holder, :usage_permission, :license_note, :rights_note,\n                :archive_name, :archive_signature, :archive_accessed_at, :keywords, :transcription_done, :transcription_type, :transcription_note, :person_status, :json_metadata\n            )\n        ");
        $stmt->execute([
            ':upload_id' => $uploadId,
            ':original_filename' => $originalFilename,
            ':stored_filename' => $storedFilename,
            ':current_filename' => $currentFilename,
            ':target_folder' => $targetFolder !== '' ? $targetFolder : null,
            ':current_path' => $currentPath !== '' ? $currentPath : null,
            ':points_eligible' => (is_point_eligible_path($targetFolder) || is_point_eligible_path($currentPath)) ? 1 : 0,
            ':uploaded_by_user_id' => $uploadOwner['id'],
            ':uploaded_by_name' => $uploadOwner['display_name'],
            ':uploaded_at' => $uploadedAt,
            ':status' => $status,
            ':document_type' => (string)($metadata['document_type'] ?? ''),
            ':source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? ''),
            ':original_location' => (string)($metadata['standort_original'] ?? $metadata['original_location'] ?? ''),
            ':document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? ''),
            ':event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? ''),
            ':place' => (string)($metadata['ort'] ?? $metadata['place'] ?? $uploadOwner['place'] ?? ''),
            ':description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? ''),
            ':note' => (string)($metadata['bemerkung'] ?? $metadata['note'] ?? ''),
            ':copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? ''),
            ':rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? ''),
            ':usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? ''),
            ':license_note' => (string)($metadata['lizenz'] ?? $metadata['license_note'] ?? ''),
            ':rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? ''),
            ':archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? ''),
            ':archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? ''),
            ':archive_accessed_at' => (string)($metadata['abruf_am'] ?? $metadata['archive_accessed_at'] ?? ''),
            ':keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? ''),
            ':transcription_done' => !empty($metadata['transcription_done']) ? 1 : 0,
            ':transcription_type' => (string)($metadata['transcription_type'] ?? ''),
            ':transcription_note' => (string)($metadata['transcription_note'] ?? ''),
            ':person_status' => (string)($input['person_status'] ?? 'none'),
            ':json_metadata' => json_encode($input, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
        ]);

        $documentId = (int)$pdo->lastInsertId();
        $history = $pdo->prepare("\n            INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details)\n            VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details)\n        ");
        $history->execute([
            ':document_id' => $documentId,
            ':upload_id' => $uploadId,
            ':user_id' => $currentUser['id'],
            ':user_display_name' => $currentUser['display_name'],
            ':action' => ($captureMode === 'existing_file_metadata' ? 'existing_file_captured' : 'document_created'),
            ':details' => ($captureMode === 'existing_file_metadata' ? 'Vorhandene Nextcloud-Datei in ODV aufgenommen' : 'Dokument wurde über API angelegt')
        ]);
        add_auto_points_for_metadata($pdo, $documentId, $uploadId, $uploadOwner, [
            'description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? ''),
            'keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? ''),
            'source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? ''),
            'usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? ''),
            'rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? ''),
            'copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? ''),
            'rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? ''),
            'archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? ''),
            'archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? ''),
            'document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? ''),
            'event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? ''),
            'transcription_done' => !empty($metadata['transcription_done']),
            'transcription_type' => (string)($metadata['transcription_type'] ?? ''),
        ], null, is_array($metadata['openai_metadata_fields'] ?? null) ? $metadata['openai_metadata_fields'] : []);
        add_special_collection_points($pdo, $documentId, $uploadId, $currentUser, $targetFolder, $currentPath, $captureMode);
        $pdo->commit();
        api_log('info', 'Dokument angelegt', ['user_id' => $currentUser['id'], 'upload_id' => $uploadId]);
        json_response(['success' => true, 'message' => 'Dokument wurde gespeichert', 'document_id' => $documentId, 'upload_id' => $uploadId], 201);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        if ((int)$e->getCode() === 23000) {
            json_response(['success' => false, 'error' => 'upload_id ist bereits vorhanden'], 409);
        }
        api_log('error', 'Dokument konnte nicht gespeichert werden', ['pdo_code' => $e->getCode(), 'upload_id' => $uploadId, 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokument konnte nicht gespeichert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/documents') {
    $currentUser = current_user();
    $pdo = db();
    try {
        $status = trim((string)($_GET['status'] ?? ''));
        $onlyOwn = (int)($_GET['only_own'] ?? 0);
        $where = [];
        $params = [];
        if ($status !== '') {
            $where[] = "status = :status";
            $params[':status'] = $status;
        } else {
            // Archivierte Dokumente bleiben erhalten, erscheinen aber nicht in Standardlisten.
            $where[] = "status <> 'archiviert'";
        }
        if ($onlyOwn === 1 && role_key($currentUser) === 'ortschronist') {
            $where[] = "uploaded_by_user_id = :user_id";
            $params[':user_id'] = $currentUser['id'];
        }
        $whereSql = count($where) > 0 ? 'WHERE ' . implode(' AND ', $where) : '';
        $stmt = $pdo->prepare("
            SELECT id, upload_id, original_filename, stored_filename, current_filename, target_folder, current_path,
                   uploaded_by_user_id, uploaded_by_name, uploaded_at, status, document_type, source, original_location, document_date,
                   event, place, description, note, copyright_author, rights_holder, usage_permission, license_note,
                   rights_note, archive_name, archive_signature, archive_accessed_at, keywords, transcription_done, transcription_type, transcription_note, person_status, json_metadata, created_at, updated_at
            FROM documents
            {$whereSql}
            ORDER BY uploaded_at DESC, id DESC
            LIMIT 500
        ");
        $stmt->execute($params);
        $documents = $stmt->fetchAll();
        if (!is_superadmin($currentUser)) {
            $filtered = [];
            foreach ($documents as $doc) {
                $pathForPermission = (string)(($doc['target_folder'] ?? '') !== '' ? $doc['target_folder'] : ($doc['current_path'] ?? ''));
                if ($pathForPermission === '' || user_has_folder_permission($pdo, $currentUser, $pathForPermission, 'read')) {
                    $filtered[] = $doc;
                }
            }
            $documents = $filtered;
        }
        json_response(['success' => true, 'documents' => $documents]);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentliste konnte nicht geladen werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokumentliste konnte nicht geladen werden'], 500);
    }
}

if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/access-log$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $rawAction = trim((string)($input['action'] ?? 'opened'));
    $action = $rawAction === 'downloaded' ? 'document_downloaded' : 'document_opened';
    $localPath = trim((string)($input['local_path'] ?? ''));
    $pdo = db();
    try {
        $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
        $stmt->execute([':upload_id' => $uploadId]);
        $document = $stmt->fetch();
        if (!$document) {
            json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
        }
        ensure_document_read_permission($pdo, $currentUser, $document);
        $details = $action === 'document_downloaded' ? 'Dokument über ODV heruntergeladen/kopiert' : 'Dokument über ODV geöffnet';
        if ($localPath !== '') {
            $details .= ': ' . basename($localPath);
        }
        $hist = $pdo->prepare("INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, new_value) VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :new_value)");
        $hist->execute([
            ':document_id' => (int)$document['id'],
            ':upload_id' => $uploadId,
            ':user_id' => (int)$currentUser['id'],
            ':user_display_name' => (string)$currentUser['display_name'],
            ':action' => $action,
            ':details' => $details,
            ':new_value' => $localPath,
        ]);
        json_response(['success' => true, 'message' => 'Dokumentzugriff protokolliert']);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentzugriff konnte nicht protokolliert werden', ['error' => $e->getMessage(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Dokumentzugriff konnte nicht protokolliert werden'], 500);
    }
}

if ($method === 'GET' && $path === '/api/document-access-log') {
    $currentUser = require_role(['Admin', 'Superadmin']);
    $pdo = db();
    $limit = max(1, min(1000, (int)($_GET['limit'] ?? 500)));
    try {
        $stmt = $pdo->prepare("\n            SELECT h.id, h.upload_id, h.user_id, h.user_display_name, h.action, h.details, h.new_value, h.created_at,\n                   d.current_filename, d.original_filename, d.current_path, d.target_folder\n            FROM document_history h\n            LEFT JOIN documents d ON d.upload_id = h.upload_id\n            WHERE h.action IN ('document_opened', 'document_downloaded')\n            ORDER BY h.created_at DESC, h.id DESC\n            LIMIT {$limit}\n        ");
        $stmt->execute();
        json_response(['success' => true, 'entries' => $stmt->fetchAll()]);
    } catch (Throwable $e) {
        api_log('error', 'Dokumentzugriffsliste konnte nicht geladen werden', ['error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Dokumentzugriffsliste konnte nicht geladen werden'], 500);
    }
}

if ($method === 'POST' && preg_match('#^/api/documents/([^/]+)/lock$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) { json_response(['success'=>false, 'error'=>'Dokument nicht gefunden'], 404); }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$document['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) { json_response(['success'=>false, 'error'=>'Keine Bearbeitungsberechtigung für dieses Dokument'], 403); }
    acquire_document_lock($pdo, $currentUser, $uploadId);
    json_response(['success'=>true, 'message'=>'Dokument wurde zur Bearbeitung gesperrt']);
}

if ($method === 'DELETE' && preg_match('#^/api/documents/([^/]+)/lock$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    ensure_security_tables($pdo);
    $stmt = $pdo->prepare("DELETE FROM odv_document_locks WHERE upload_id=:upload_id AND (locked_by_user_id=:uid OR :is_admin=1)");
    $stmt->execute([':upload_id'=>$uploadId, ':uid'=>(int)$currentUser['id'], ':is_admin'=>is_superadmin($currentUser) ? 1 : 0]);
    json_response(['success'=>true, 'message'=>'Dokumentsperre gelöst']);
}

if ($method === 'GET' && preg_match('#^/api/documents/([^/]+)$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    ensure_document_read_permission($pdo, $currentUser, $document);
    $historyStmt = $pdo->prepare("\n        SELECT id, user_display_name, action, details, old_value, new_value, created_at\n        FROM document_history\n        WHERE upload_id = :upload_id\n        ORDER BY created_at ASC, id ASC\n    ");
    $historyStmt->execute([':upload_id' => $uploadId]);
    $personsStmt = $pdo->prepare("\n        SELECT id, number, display_name, x, y, certainty, note, created_by_name, created_at, updated_at\n        FROM document_persons\n        WHERE document_id = :document_id\n        ORDER BY number ASC\n    ");
    $personsStmt->execute([':document_id' => $document['id']]);
    json_response([
        'success' => true,
        'document' => $document,
        'persons' => $personsStmt->fetchAll(),
        'history' => $historyStmt->fetchAll()
    ]);
}

if ($method === 'PUT' && preg_match('#^/api/documents/([^/]+)$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $existing = $stmt->fetch();
    if (!$existing) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$existing['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) {
        json_response(['success' => false, 'error' => 'Keine Berechtigung für dieses Dokument'], 403);
    }
    acquire_document_lock($pdo, $currentUser, $uploadId);
    $metadata = is_array($input['metadata'] ?? null) ? $input['metadata'] : [];
    $captureMode = trim((string)($input['odv_capture_mode'] ?? 'odv_upload'));
    $newValues = [
        'current_filename' => trim((string)($input['current_filename'] ?? $existing['current_filename'])),
        'target_folder' => trim((string)($input['target_folder'] ?? $existing['target_folder'])),
        'current_path' => trim((string)($input['current_path'] ?? $existing['current_path'])),
        'status' => validate_document_status(trim((string)($input['status'] ?? $existing['status']))),
        'document_type' => (string)($metadata['document_type'] ?? $input['document_type'] ?? $existing['document_type']),
        'source' => (string)($metadata['quelle'] ?? $metadata['source'] ?? $input['source'] ?? $existing['source']),
        'original_location' => (string)($metadata['standort_original'] ?? $metadata['original_location'] ?? $input['original_location'] ?? $existing['original_location']),
        'document_date' => (string)($metadata['datum'] ?? $metadata['document_date'] ?? $input['document_date'] ?? $existing['document_date']),
        'event' => (string)($metadata['ereignis'] ?? $metadata['event'] ?? $input['event'] ?? $existing['event']),
        'place' => (string)($metadata['ort'] ?? $metadata['place'] ?? $input['place'] ?? $existing['place']),
        'description' => (string)($metadata['beschreibung'] ?? $metadata['description'] ?? $input['description'] ?? $existing['description']),
        'note' => (string)($metadata['bemerkung'] ?? $metadata['note'] ?? $input['note'] ?? $existing['note']),
        'copyright_author' => (string)($metadata['urheber'] ?? $metadata['copyright_author'] ?? $input['copyright_author'] ?? $existing['copyright_author']),
        'rights_holder' => (string)($metadata['rechteinhaber'] ?? $metadata['rights_holder'] ?? $input['rights_holder'] ?? $existing['rights_holder']),
        'usage_permission' => (string)($metadata['nutzungsfreigabe'] ?? $metadata['usage_permission'] ?? $input['usage_permission'] ?? $existing['usage_permission']),
        'license_note' => (string)($metadata['lizenz'] ?? $metadata['license_note'] ?? $input['license_note'] ?? $existing['license_note']),
        'rights_note' => (string)($metadata['rechte'] ?? $metadata['rights_note'] ?? $input['rights_note'] ?? $existing['rights_note']),
        'archive_name' => (string)($metadata['archiv'] ?? $metadata['archive_name'] ?? $input['archive_name'] ?? $existing['archive_name']),
        'archive_signature' => (string)($metadata['signatur'] ?? $metadata['archive_signature'] ?? $input['archive_signature'] ?? $existing['archive_signature']),
        'archive_accessed_at' => (string)($metadata['abruf_am'] ?? $metadata['archive_accessed_at'] ?? $input['archive_accessed_at'] ?? $existing['archive_accessed_at']),
        'keywords' => (string)($metadata['stichwoerter'] ?? $metadata['keywords'] ?? $input['keywords'] ?? $existing['keywords'] ?? ''),
        'transcription_done' => !empty($metadata['transcription_done'] ?? $input['transcription_done'] ?? $existing['transcription_done'] ?? 0) ? 1 : 0,
        'transcription_type' => (string)($metadata['transcription_type'] ?? $input['transcription_type'] ?? $existing['transcription_type'] ?? ''),
        'transcription_note' => (string)($metadata['transcription_note'] ?? $input['transcription_note'] ?? $existing['transcription_note'] ?? ''),
        'person_status' => (string)($input['person_status'] ?? $existing['person_status']),
        'json_metadata' => json_encode($input, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
    ];
    $newUploadedByUserId = (int)($existing['uploaded_by_user_id'] ?? 0);
    $newUploadedByName = (string)($existing['uploaded_by_name'] ?? '');
    if ($isAdmin && isset($input['uploaded_by_user_id']) && (int)$input['uploaded_by_user_id'] > 0) {
        $uStmt = $pdo->prepare("SELECT id, display_name FROM users WHERE id = :id LIMIT 1");
        $uStmt->execute([':id' => (int)$input['uploaded_by_user_id']]);
        $uRow = $uStmt->fetch();
        if ($uRow) {
            $newUploadedByUserId = (int)$uRow['id'];
            $newUploadedByName = (string)$uRow['display_name'];
        }
    }
    if (!$isAdmin) {
        if ($newValues['status'] !== $existing['status']) {
            json_response(['success' => false, 'error' => 'Status darf nur durch Admins geändert werden'], 403);
        }
        if ((string)$newValues['target_folder'] !== (string)($existing['target_folder'] ?? '')) {
            json_response(['success' => false, 'error' => 'Zielordner darf nur durch Admins geändert werden'], 403);
        }
        $oldPathNorm = str_replace('\\', '/', (string)($existing['current_path'] ?? ''));
        $newPathNorm = str_replace('\\', '/', (string)($newValues['current_path'] ?? ''));
        $oldDir = dirname($oldPathNorm);
        $newDir = dirname($newPathNorm);
        if ($oldDir !== $newDir) {
            json_response(['success' => false, 'error' => 'Dateien dürfen nur durch Admins verschoben werden'], 403);
        }
    }

    $permissionDoc = $existing;
    $permissionDoc['target_folder'] = $newValues['target_folder'];
    $permissionDoc['current_path'] = $newValues['current_path'];
    ensure_document_write_permission($pdo, $currentUser, $permissionDoc);

    try {
        $pdo->beginTransaction();
        $update = $pdo->prepare("\n            UPDATE documents SET\n                current_filename = :current_filename, target_folder = :target_folder, current_path = :current_path, status = :status,\n                uploaded_by_user_id = :uploaded_by_user_id, uploaded_by_name = :uploaded_by_name,\n                document_type = :document_type, source = :source, original_location = :original_location, document_date = :document_date,\n                event = :event, place = :place, description = :description, note = :note,\n                copyright_author = :copyright_author, rights_holder = :rights_holder, usage_permission = :usage_permission,\n                license_note = :license_note, rights_note = :rights_note, archive_name = :archive_name, archive_signature = :archive_signature,\n                archive_accessed_at = :archive_accessed_at, keywords = :keywords, transcription_done = :transcription_done, transcription_type = :transcription_type, transcription_note = :transcription_note, person_status = :person_status, json_metadata = :json_metadata\n            WHERE upload_id = :upload_id\n        ");
        $update->execute([
            ':upload_id' => $uploadId,
            ':current_filename' => $newValues['current_filename'],
            ':target_folder' => $newValues['target_folder'] !== '' ? $newValues['target_folder'] : null,
            ':current_path' => $newValues['current_path'] !== '' ? $newValues['current_path'] : null,
            ':status' => $newValues['status'],
            ':uploaded_by_user_id' => $newUploadedByUserId,
            ':uploaded_by_name' => $newUploadedByName,
            ':document_type' => $newValues['document_type'],
            ':source' => $newValues['source'],
            ':original_location' => $newValues['original_location'],
            ':document_date' => $newValues['document_date'],
            ':event' => $newValues['event'],
            ':place' => $newValues['place'],
            ':description' => $newValues['description'],
            ':note' => $newValues['note'],
            ':copyright_author' => $newValues['copyright_author'],
            ':rights_holder' => $newValues['rights_holder'],
            ':usage_permission' => $newValues['usage_permission'],
            ':license_note' => $newValues['license_note'],
            ':rights_note' => $newValues['rights_note'],
            ':archive_name' => $newValues['archive_name'],
            ':archive_signature' => $newValues['archive_signature'],
            ':archive_accessed_at' => $newValues['archive_accessed_at'],
            ':keywords' => $newValues['keywords'],
            ':transcription_done' => $newValues['transcription_done'],
            ':transcription_type' => $newValues['transcription_type'],
            ':transcription_note' => $newValues['transcription_note'],
            ':person_status' => $newValues['person_status'],
            ':json_metadata' => $newValues['json_metadata'],
        ]);
        $changes = [];
        foreach ($newValues as $field => $newValue) {
            if ($field === 'json_metadata') {
                continue;
            }
            $oldValue = (string)($existing[$field] ?? '');
            if ((string)$newValue !== $oldValue) {
                $changes[] = ['field' => $field, 'old' => $oldValue, 'new' => (string)$newValue];
            }
        }
        if ($newUploadedByUserId !== (int)($existing['uploaded_by_user_id'] ?? 0)) {
            $changes[] = ['field' => 'uploaded_by', 'old' => (string)($existing['uploaded_by_name'] ?? ''), 'new' => $newUploadedByName];
            // Automatische, dem bisherigen Hochlader gutgeschriebene Punkte werden auf den neuen Hochlader übertragen.
            $transfer = $pdo->prepare("UPDATE contribution_points SET user_id = :new_user_id, user_display_name = :new_name WHERE document_id = :document_id AND user_id = :old_user_id AND is_manual = 0");
            $transfer->execute([':new_user_id' => $newUploadedByUserId, ':new_name' => $newUploadedByName, ':document_id' => (int)$existing['id'], ':old_user_id' => (int)($existing['uploaded_by_user_id'] ?? 0)]);
        }
        if (count($changes) > 0) {
            $history = $pdo->prepare("\n                INSERT INTO document_history (document_id, upload_id, user_id, user_display_name, action, details, old_value, new_value)\n                VALUES (:document_id, :upload_id, :user_id, :user_display_name, :action, :details, :old_value, :new_value)\n            ");
            foreach ($changes as $change) {
                $history->execute([
                    ':document_id' => $existing['id'],
                    ':upload_id' => $uploadId,
                    ':user_id' => $currentUser['id'],
                    ':user_display_name' => $currentUser['display_name'],
                    ':action' => 'document_updated',
                    ':details' => 'Feld geändert: ' . $change['field'],
                    ':old_value' => $change['old'],
                    ':new_value' => $change['new'],
                ]);
            }
        }
        add_auto_points_for_metadata($pdo, (int)$existing['id'], $uploadId, $currentUser, $newValues, $existing, is_array($metadata['openai_metadata_fields'] ?? null) ? $metadata['openai_metadata_fields'] : []);
        if (($newValues['status'] ?? '') === 'erfasst' && ($existing['status'] ?? '') !== 'erfasst') {
            add_contribution_point($pdo, (int)$existing['id'], $uploadId, $currentUser, $currentUser, 'admin_review', 'admin_review_accepted', 'Dokument erfasst', 'status', point_rule_points($pdo, current_points_year(), 'admin_review_accepted', 1), false);
        }
        if ((string)($newValues['current_path'] ?? '') !== (string)($existing['current_path'] ?? '') || (string)($newValues['current_filename'] ?? '') !== (string)($existing['current_filename'] ?? '')) {
            add_contribution_point($pdo, (int)$existing['id'], $uploadId, $currentUser, $currentUser, 'admin_review', 'admin_file_organization', 'Datei umbenannt oder verschoben', 'current_path', point_rule_points($pdo, current_points_year(), 'admin_file_organization', 1), false);
        }
        $pdo->commit();
        json_response(['success' => true, 'message' => 'Dokument wurde aktualisiert', 'upload_id' => $uploadId, 'changes' => $changes]);
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        api_log('error', 'Dokument konnte nicht aktualisiert werden', ['pdo_code' => $e->getCode(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Dokument konnte nicht aktualisiert werden'], 500);
    }
}

if ($method === 'PUT' && preg_match('#^/api/documents/([^/]+)/persons$#', $path, $matches)) {
    $currentUser = current_user();
    $uploadId = urldecode($matches[1]);
    $input = get_json_input();
    $persons = $input['persons'] ?? null;
    if (!is_array($persons)) {
        json_response(['success' => false, 'error' => 'persons muss ein Array sein'], 400);
    }
    $pdo = db();
    $stmt = $pdo->prepare("SELECT * FROM documents WHERE upload_id = :upload_id LIMIT 1");
    $stmt->execute([':upload_id' => $uploadId]);
    $document = $stmt->fetch();
    if (!$document) {
        json_response(['success' => false, 'error' => 'Dokument nicht gefunden'], 404);
    }
    $isAdmin = is_admin_role($currentUser);
    $isOwner = ((int)$document['uploaded_by_user_id'] === (int)$currentUser['id']);
    if (!$isAdmin && !$isOwner) {
        json_response(['success' => false, 'error' => 'Keine Berechtigung für dieses Dokument'], 403);
    }
    ensure_document_write_permission($pdo, $currentUser, $document);
    try {
        $pdo->beginTransaction();
        $delete = $pdo->prepare("DELETE FROM document_persons WHERE document_id = :document_id");
        $delete->execute([':document_id' => $document['id']]);
        $insert = $pdo->prepare("\n            INSERT INTO document_persons (document_id, number, display_name, x, y, certainty, note, created_by_user_id, created_by_name)\n            VALUES (:document_id, :number, :display_name, :x, :y, :certainty, :note, :created_by_user_id, :created_by_name)\n        ");
        $count = 0;
        foreach ($persons as $person) {
            if (!is_array($person)) {
                continue;
            }
            $number = (int)($person['number'] ?? 0);
            $displayName = trim((string)($person['display_name'] ?? ''));
            if ($number <= 0 || $displayName === '') {
                continue;
            }
            $insert->execute([
                ':document_id' => $document['id'],
                ':number' => $number,
                ':display_name' => $displayName,
                ':x' => isset($person['x']) ? (float)$person['x'] : null,
                ':y' => isset($person['y']) ? (float)$person['y'] : null,
                ':certainty' => isset($person['certainty']) ? (float)$person['certainty'] : null,
                ':note' => trim((string)($person['note'] ?? '')),
                ':created_by_user_id' => $currentUser['id'],
                ':created_by_name' => $currentUser['display_name'],
            ]);
            $count++;
        }
        if (in_array((string)($document['status'] ?? ''), ['erfasst', 'geprueft', 'archiviert'], true)) {
            $events = document_person_events_from_payload($document, $persons);
            add_person_points_for_document($pdo, (int)$document['id'], $uploadId, $currentUser, $document, $events);
        }
        $pdo->commit();
        json_response(['success' => true, 'message' => 'Personen gespeichert', 'count' => $count]);
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        api_log('error', 'Personen konnten nicht gespeichert werden', ['error' => $e->getMessage(), 'upload_id' => $uploadId]);
        json_response(['success' => false, 'error' => 'Personen konnten nicht gespeichert werden'], 500);
    }
}
