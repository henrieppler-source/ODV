<?php
declare(strict_types=1);

if ($method === 'GET' && $path === '/api/admin/maintenance') {
    $currentUser = current_user();
    $pdo = db();
    json_response(['success' => true, 'maintenance' => maintenance_state($pdo)]);
}

if ($method === 'GET' && $path === '/api/admin/operating-mode') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $mode = operating_mode($pdo);
    json_response(['success' => true, 'mode' => $mode, 'label' => operating_mode_label($mode)]);
}

if ($method === 'POST' && $path === '/api/admin/operating-mode') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $input = get_json_input();
    $mode = strtolower(trim((string)($input['mode'] ?? 'production')));
    if (!in_array($mode, ['production', 'test'], true)) {
        json_response(['success' => false, 'error' => 'Ungültiger Betriebsmodus'], 400);
    }
    setting_set($pdo, 'operating_mode', $mode);
    api_log('warning', 'Betriebsmodus geändert', ['by_user_id' => $currentUser['id'], 'mode' => $mode]);
    json_response(['success' => true, 'mode' => $mode, 'label' => operating_mode_label($mode)]);
}

if ($method === 'POST' && $path === '/api/admin/maintenance') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $input = get_json_input();
    $action = trim((string)($input['action'] ?? 'schedule'));
    if ($action === 'clear') {
        setting_set($pdo, 'maintenance_enabled', '0');
        setting_delete($pdo, 'maintenance_starts_at');
        api_log('warning', 'Wartungsmodus beendet', ['by_user_id' => $currentUser['id']]);
        json_response(['success' => true, 'maintenance' => maintenance_state($pdo)]);
    }
    $minutes = max(0, (int)($input['minutes'] ?? 0));
    $startsAt = date('Y-m-d H:i:s', time() + ($minutes * 60));
    $message = trim((string)($input['message'] ?? ''));
    if ($message === '') { $message = 'Die ODV-Datenbank ist wegen Wartungsarbeiten gesperrt. Bitte versuchen Sie es später erneut.'; }
    setting_set($pdo, 'maintenance_enabled', '1');
    setting_set($pdo, 'maintenance_starts_at', $startsAt);
    setting_set($pdo, 'maintenance_message', $message);
    setting_set($pdo, 'maintenance_started_by', (string)$currentUser['id']);
    api_log('warning', 'Wartungsmodus geplant', ['by_user_id' => $currentUser['id'], 'starts_at' => $startsAt, 'minutes' => $minutes]);
    json_response(['success' => true, 'maintenance' => maintenance_state($pdo)]);
}

if ($method === 'GET' && $path === '/api/admin/nextcloud-settings') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $baseUrl = trim((string)(setting_get($pdo, 'nextcloud_base_url', '') ?? ''));
    if ($baseUrl === '') {
        $baseUrl = server_env_value('NEXTCLOUD_BASE_URL', 'https://nx94165.your-storageshare.de');
    }
    $webFilesUrl = trim((string)(setting_get($pdo, 'nextcloud_web_files_url', '') ?? ''));
    if ($webFilesUrl === '') {
        $webFilesUrl = rtrim($baseUrl, '/') . '/apps/files/files';
    }
    $username = trim((string)(setting_get($pdo, 'nextcloud_technical_username', '') ?? ''));
    if ($username === '') {
        $username = server_env_value('NEXTCLOUD_USERNAME');
    }
    $remoteBase = trim((string)(setting_get($pdo, 'nextcloud_remote_base', '') ?? ''));
    if ($remoteBase === '') {
        $remoteBase = server_env_value('NEXTCLOUD_REMOTE_BASE');
    }
    $passwordSaved = trim((string)(setting_get($pdo, 'nextcloud_technical_password_enc', '') ?? '')) !== ''
        || server_env_value('NEXTCLOUD_APP_PASSWORD') !== '';
    json_response([
        'success' => true,
        'settings' => [
            'base_url' => $baseUrl,
            'web_files_url' => $webFilesUrl,
            'username' => $username,
            'remote_base' => $remoteBase,
            'password_saved' => $passwordSaved,
            'source' => trim((string)(setting_get($pdo, 'nextcloud_technical_username', '') ?? '')) !== '' ? 'database' : 'env',
        ],
    ]);
}

if ($method === 'PUT' && $path === '/api/admin/nextcloud-settings') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $input = get_json_input();
    $baseUrl = trim((string)($input['base_url'] ?? ''));
    $webFilesUrl = trim((string)($input['web_files_url'] ?? ''));
    $username = trim((string)($input['username'] ?? ''));
    $remoteBase = trim(str_replace('\\', '/', (string)($input['remote_base'] ?? '')), '/');
    $password = (string)($input['password'] ?? '');
    if ($baseUrl === '' || !filter_var($baseUrl, FILTER_VALIDATE_URL)) {
        json_response(['success' => false, 'error' => 'Nextcloud-Basis-URL ist ungültig.'], 400);
    }
    if ($webFilesUrl !== '' && !filter_var($webFilesUrl, FILTER_VALIDATE_URL)) {
        json_response(['success' => false, 'error' => 'Nextcloud Web-Dateiansicht ist ungültig.'], 400);
    }
    if ($username === '') {
        json_response(['success' => false, 'error' => 'Technischer Nextcloud-Benutzer fehlt.'], 400);
    }
    setting_set($pdo, 'nextcloud_base_url', $baseUrl);
    setting_set($pdo, 'nextcloud_web_files_url', $webFilesUrl);
    setting_set($pdo, 'nextcloud_technical_username', $username);
    setting_set($pdo, 'nextcloud_remote_base', $remoteBase);
    if ($password !== '') {
        setting_set($pdo, 'nextcloud_technical_password_enc', encrypt_nextcloud_credential($pdo, $password));
    }
    api_log('warning', 'Technische Nextcloud-Einstellungen gespeichert', [
        'by_user_id' => $currentUser['id'],
        'base_url' => $baseUrl,
        'web_files_url' => $webFilesUrl,
        'username' => $username,
        'remote_base' => $remoteBase,
        'password_changed' => $password !== '',
    ]);
    json_response([
        'success' => true,
        'settings' => [
            'base_url' => $baseUrl,
            'web_files_url' => $webFilesUrl,
            'username' => $username,
            'remote_base' => $remoteBase,
            'password_saved' => $password !== ''
                || trim((string)(setting_get($pdo, 'nextcloud_technical_password_enc', '') ?? '')) !== ''
                || server_env_value('NEXTCLOUD_APP_PASSWORD') !== '',
            'source' => 'database',
        ],
    ]);
}

if ($method === 'POST' && $path === '/api/admin/nextcloud-settings/test') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $input = get_json_input();
    $baseUrl = trim((string)($input['base_url'] ?? ''));
    $webFilesUrl = trim((string)($input['web_files_url'] ?? ''));
    $username = trim((string)($input['username'] ?? ''));
    $password = (string)($input['password'] ?? '');
    if ($baseUrl === '' || !filter_var($baseUrl, FILTER_VALIDATE_URL)) {
        json_response(['success' => false, 'error' => 'Nextcloud-Basis-URL ist ungültig.'], 400);
    }
    if ($username === '') {
        json_response(['success' => false, 'error' => 'Technischer Nextcloud-Benutzer fehlt.'], 400);
    }
    if ($password === '') {
        $passwordEnc = trim((string)(setting_get($pdo, 'nextcloud_technical_password_enc', '') ?? ''));
        if ($passwordEnc !== '') {
            $password = decrypt_nextcloud_credential($pdo, $passwordEnc);
        } else {
            $password = server_env_value('NEXTCLOUD_APP_PASSWORD');
        }
    }
    if ($password === '') {
        json_response(['success' => false, 'error' => 'Kein Nextcloud-App-Passwort gespeichert oder eingegeben.'], 400);
    }

    try {
        $parts = parse_url($baseUrl);
        if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) {
            throw new RuntimeException('Nextcloud-Basis-URL ist ungültig.');
        }
        $root = $parts['scheme'] . '://' . $parts['host'];
        if (!empty($parts['port'])) {
            $root .= ':' . $parts['port'];
        }
        $url = rtrim($root, '/') . '/remote.php/dav/files/' . rawurlencode($username) . '/';
        nextcloud_webdav_request('PROPFIND', $url, $username, $password, '', ['Depth: 0']);
        api_log('info', 'Technischer Nextcloud-Zugang geprüft', ['by_user_id' => $currentUser['id'], 'username' => $username, 'base_url' => $baseUrl]);
        json_response(['success' => true, 'message' => 'Nextcloud-Verbindung OK.']);
    } catch (Throwable $e) {
        api_log('warning', 'Technischer Nextcloud-Zugang fehlgeschlagen', [
            'by_user_id' => $currentUser['id'],
            'username' => $username,
            'base_url' => $baseUrl,
            'error' => $e->getMessage(),
        ]);
        json_response(['success' => false, 'error' => 'Nextcloud-Test fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}

if ($method === 'POST' && $path === '/api/admin/backup') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    try {
        $backup = create_pdo_database_backup($pdo, $currentUser);
        json_response(['success' => true, 'backup' => $backup]);
    } catch (Throwable $e) {
        api_log('error', 'Datenbanksicherung fehlgeschlagen', ['by_user_id' => $currentUser['id'], 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Datenbanksicherung fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}

if ($method === 'GET' && $path === '/api/admin/backup-status') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $latest = latest_backup_info($pdo);
    $ageHours = null;
    $warning = true;
    if ($latest && !empty($latest['created_at'])) {
        $ts = strtotime((string)$latest['created_at']);
        if ($ts) {
            $ageHours = round((time() - $ts) / 3600, 1);
            $warning = $ageHours > 48;
        }
    }
    json_response(['success' => true, 'latest' => $latest, 'age_hours' => $ageHours, 'warning' => $warning]);
}

if ($method === 'GET' && $path === '/api/admin/backups') {
    $currentUser = require_role(['superadmin']);
    json_response(['success' => true, 'backups' => list_database_backups()]);
}

if ($method === 'POST' && $path === '/api/admin/restore-backup') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $file = trim((string)($input['file'] ?? ''));
    $confirm = trim((string)($input['confirm_text'] ?? ''));
    if ($confirm !== 'BACKUP ZURUECKSICHERN') {
        json_response(['success' => false, 'error' => 'Sicherheitsabfrage nicht erfüllt'], 400);
    }
    if ($file === '') {
        json_response(['success' => false, 'error' => 'Keine Backup-Datei ausgewählt'], 400);
    }
    $pdo = db();
    try {
        $before = create_pdo_database_backup($pdo, $currentUser);
        $restore = restore_database_backup($pdo, $file);
        api_log('warning', 'Datenbankbackup zurückgesichert', ['by_user_id' => $currentUser['id'], 'file' => $file, 'before_backup' => $before['file'] ?? '']);
        json_response(['success' => true, 'before_backup' => $before, 'restore' => $restore]);
    } catch (Throwable $e) {
        api_log('error', 'Backup-Rücksicherung fehlgeschlagen', ['by_user_id' => $currentUser['id'], 'file' => $file, 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Backup-Rücksicherung fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}

if ($method === 'GET' && $path === '/api/admin/schema-migrations') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    $migrations = available_schema_migrations($pdo);
    $pending = array_values(array_filter($migrations, fn($m) => !empty($m['pending'])));
    json_response([
        'success' => true,
        'api_version' => ODV_API_VERSION,
        'migrations' => $migrations,
        'pending_count' => count($pending),
        'latest_backup' => latest_backup_info($pdo),
    ]);
}

if ($method === 'POST' && $path === '/api/admin/schema-migrations/apply') {
    $currentUser = require_role(['superadmin']);
    $pdo = db();
    try {
        $backup = create_pdo_database_backup($pdo, $currentUser);
        $applied = apply_schema_migrations($pdo, $currentUser);
        $migrations = available_schema_migrations($pdo);
        $pending = array_values(array_filter($migrations, fn($m) => !empty($m['pending'])));
        api_log('warning', 'Datenbankmigrationen ausgefuehrt', ['by_user_id' => $currentUser['id'], 'applied' => $applied]);
        json_response([
            'success' => true,
            'api_version' => ODV_API_VERSION,
            'backup' => $backup,
            'latest_backup' => $backup,
            'applied' => $applied,
            'migrations' => $migrations,
            'pending_count' => count($pending),
        ]);
    } catch (Throwable $e) {
        api_log('error', 'Datenbankmigration fehlgeschlagen', ['by_user_id' => $currentUser['id'], 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Datenbankmigration fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}

if ($method === 'POST' && $path === '/api/admin/reset-database') {
    $currentUser = require_role(['superadmin']);
    $input = get_json_input();
    $confirm = trim((string)($input['confirm_text'] ?? ''));
    if ($confirm !== 'DATENBANK ZURUECKSETZEN') {
        json_response(['success' => false, 'error' => 'Sicherheitsabfrage nicht erfüllt'], 400);
    }
    $includeMail = !empty($input['include_mail_history']);
    $pdo = db();
    if (operating_mode($pdo) !== 'test') {
        json_response(['success' => false, 'error' => 'Datenbank-Reset ist nur im Testbetrieb erlaubt.'], 403);
    }
    try {
        // Sicherheitsnetz: Vor jedem Reset automatisch ein aktuelles Datenbankbackup erstellen.
        create_pdo_database_backup($pdo, $currentUser);
    } catch (Throwable $e) {
        json_response(['success' => false, 'error' => 'Reset wurde abgebrochen, weil das vorherige Backup fehlgeschlagen ist: ' . $e->getMessage()], 500);
    }
    $deleted = [];
    try {
        $pdo->exec("SET FOREIGN_KEY_CHECKS = 0");
        $tables = [
            'contribution_points',
            'point_events',
            'point_adjustments',
            'manual_special_points',
            'document_persons',
            'document_history',
            'documents',
        ];
        if ($includeMail) {
            $tables[] = 'mail_history';
        }
        foreach ($tables as $table) {
            if (db_table_exists($pdo, $table)) {
                $pdo->exec("TRUNCATE TABLE `$table`");
                $deleted[$table] = 1;
            }
        }
        $pdo->exec("SET FOREIGN_KEY_CHECKS = 1");
        api_log('warning', 'Datenbank-Reset ausgeführt', ['by_user_id' => $currentUser['id'], 'include_mail' => $includeMail ? 1 : 0]);
        json_response(['success' => true, 'deleted' => $deleted]);
    } catch (Throwable $e) {
        try {
            $pdo->exec("SET FOREIGN_KEY_CHECKS = 1");
        } catch (Throwable $ignore) {}
        api_log('error', 'Datenbank-Reset fehlgeschlagen', ['by_user_id' => $currentUser['id'], 'error' => $e->getMessage()]);
        json_response(['success' => false, 'error' => 'Datenbank-Reset fehlgeschlagen: ' . $e->getMessage()], 500);
    }
}
