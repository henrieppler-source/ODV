<?php

declare(strict_types=1);

function ensure_system_settings_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS system_settings (
        setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
        setting_value TEXT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

function setting_get(PDO $pdo, string $key, ?string $default = null): ?string
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1");
    $stmt->execute([':k' => $key]);
    $value = $stmt->fetchColumn();
    return $value === false ? $default : (string)$value;
}

function setting_set(PDO $pdo, string $key, string $value): void
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("INSERT INTO system_settings (setting_key, setting_value) VALUES (:k, :v)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_at = NOW()");
    $stmt->execute([':k' => $key, ':v' => $value]);
}

function ensure_user_nextcloud_columns(PDO $pdo): void
{
    if (!db_column_exists($pdo, 'users', 'nextcloud_username')) {
        $pdo->exec("ALTER TABLE users ADD COLUMN nextcloud_username VARCHAR(255) NULL AFTER email");
    }
    if (!db_column_exists($pdo, 'users', 'nextcloud_password_enc')) {
        $pdo->exec("ALTER TABLE users ADD COLUMN nextcloud_password_enc TEXT NULL AFTER nextcloud_username");
    }
}

function ensure_user_folder_permissions_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS user_folder_permissions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        folder_group VARCHAR(80) NOT NULL,
        can_read TINYINT(1) NOT NULL DEFAULT 0,
        can_write TINYINT(1) NOT NULL DEFAULT 0,
        updated_by_user_id INT DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_user_folder_group (user_id, folder_group),
        CONSTRAINT fk_ufp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_ufp_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function ensure_place_folders_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS place_folders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        place VARCHAR(150) NOT NULL UNIQUE,
        folder_name VARCHAR(255) NOT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        updated_by_user_id INT DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        CONSTRAINT fk_place_folders_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function ensure_mail_group_external_table(PDO $pdo): void
{
    ensure_mail_group_tables($pdo);
    $pdo->exec("CREATE TABLE IF NOT EXISTS mail_group_external_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL,
        first_name VARCHAR(255) DEFAULT NULL,
        last_name VARCHAR(255) DEFAULT NULL,
        email VARCHAR(255) NOT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_mgem_group (group_id),
        INDEX idx_mgem_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

function ensure_mail_group_tables(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS mail_groups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL UNIQUE,
        description TEXT DEFAULT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_by_user_id INT DEFAULT NULL,
        created_by_display_name VARCHAR(200) DEFAULT NULL,
        created_by_role VARCHAR(40) DEFAULT NULL,
        created_by_place VARCHAR(200) DEFAULT NULL,
        updated_by_user_id INT DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_mail_groups_creator (created_by_user_id),
        INDEX idx_mail_groups_creator_place (created_by_place),
        CONSTRAINT fk_mail_groups_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
    $pdo->exec("CREATE TABLE IF NOT EXISTS mail_group_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL,
        user_id INT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_group_user (group_id, user_id),
        CONSTRAINT fk_mgm_group FOREIGN KEY (group_id) REFERENCES mail_groups(id) ON DELETE CASCADE,
        CONSTRAINT fk_mgm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function ensure_mail_group_creator_columns(PDO $pdo): void
{
    if (!db_column_exists($pdo, 'mail_groups', 'created_by_user_id')) {
        $pdo->exec("ALTER TABLE mail_groups ADD COLUMN created_by_user_id INT DEFAULT NULL AFTER is_active");
    }
    if (!db_column_exists($pdo, 'mail_groups', 'created_by_display_name')) {
        $pdo->exec("ALTER TABLE mail_groups ADD COLUMN created_by_display_name VARCHAR(200) DEFAULT NULL AFTER created_by_user_id");
    }
    if (!db_column_exists($pdo, 'mail_groups', 'created_by_role')) {
        $pdo->exec("ALTER TABLE mail_groups ADD COLUMN created_by_role VARCHAR(40) DEFAULT NULL AFTER created_by_display_name");
    }
    if (!db_column_exists($pdo, 'mail_groups', 'created_by_place')) {
        $pdo->exec("ALTER TABLE mail_groups ADD COLUMN created_by_place VARCHAR(200) DEFAULT NULL AFTER created_by_role");
    }
}

function nextcloud_credentials_crypto_key(PDO $pdo): string
{
    ensure_system_settings_table($pdo);
    $stored = trim((string)(setting_get($pdo, 'nextcloud_credentials_crypto_key', '') ?? ''));
    if ($stored === '') {
        $stored = bin2hex(random_bytes(32));
        setting_set($pdo, 'nextcloud_credentials_crypto_key', $stored);
    }
    return hash('sha256', $stored, true);
}

function encrypt_nextcloud_credential(PDO $pdo, string $value): string
{
    $plain = trim($value);
    if ($plain === '') {
        return '';
    }
    if (!function_exists('openssl_encrypt')) {
        throw new RuntimeException('OpenSSL ist auf dem Server nicht verfügbar.');
    }
    $key = nextcloud_credentials_crypto_key($pdo);
    $iv = random_bytes(12);
    $tag = '';
    $cipher = openssl_encrypt($plain, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
    if ($cipher === false) {
        throw new RuntimeException('Nextcloud-Zugangsdaten konnten nicht verschlüsselt werden.');
    }
    return 'nc1:' . base64_encode($iv . $tag . $cipher);
}

function decrypt_nextcloud_credential(PDO $pdo, string $value): string
{
    $stored = trim($value);
    if ($stored === '') {
        return '';
    }
    if (!str_starts_with($stored, 'nc1:')) {
        return $stored;
    }
    if (!function_exists('openssl_decrypt')) {
        throw new RuntimeException('OpenSSL ist auf dem Server nicht verfügbar.');
    }
    $raw = base64_decode(substr($stored, 4), true);
    if ($raw === false || strlen($raw) < 29) {
        throw new RuntimeException('Gespeicherte Nextcloud-Zugangsdaten sind ungültig.');
    }
    $iv = substr($raw, 0, 12);
    $tag = substr($raw, 12, 16);
    $cipher = substr($raw, 28);
    $key = nextcloud_credentials_crypto_key($pdo);
    $plain = openssl_decrypt($cipher, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
    if ($plain === false) {
        throw new RuntimeException('Gespeicherte Nextcloud-Zugangsdaten konnten nicht entschlüsselt werden.');
    }
    return $plain;
}

function setting_delete(PDO $pdo, string $key): void
{
    ensure_system_settings_table($pdo);
    $stmt = $pdo->prepare("DELETE FROM system_settings WHERE setting_key = :k");
    $stmt->execute([':k' => $key]);
}

function operating_mode(PDO $pdo): string
{
    $mode = strtolower(trim((string)setting_get($pdo, 'operating_mode', 'production')));
    return $mode === 'test' ? 'test' : 'production';
}

function operating_mode_label(string $mode): string
{
    return $mode === 'test' ? 'Testbetrieb' : 'Produktivbetrieb';
}


function ensure_manual_special_points_table(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS manual_special_points (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        user_display_name VARCHAR(200) NOT NULL,
        points_year INT NOT NULL,
        activity_date DATE DEFAULT NULL,
        rule_key VARCHAR(120) NOT NULL,
        rule_label VARCHAR(255) NOT NULL,
        hours DECIMAL(8,2) DEFAULT NULL,
        points INT NOT NULL,
        reason TEXT NOT NULL,
        note TEXT DEFAULT NULL,
        created_by_user_id INT DEFAULT NULL,
        created_by_name VARCHAR(200) DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_msp_year (points_year),
        INDEX idx_msp_user_year (user_id, points_year),
        INDEX idx_msp_created_by (created_by_user_id),
        CONSTRAINT fk_msp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_msp_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
}

function maintenance_state(PDO $pdo): array
{
    $enabled = setting_get($pdo, 'maintenance_enabled', '0') === '1';
    $startsAt = setting_get($pdo, 'maintenance_starts_at', '');
    $message = setting_get($pdo, 'maintenance_message', 'Die ODV-Datenbank ist wegen Wartungsarbeiten gesperrt.');
    $startsTs = $startsAt ? strtotime($startsAt) : false;
    $active = $enabled && (!$startsTs || $startsTs <= time());
    $scheduled = $enabled && $startsTs && $startsTs > time();
    $minutesLeft = $scheduled ? max(0, (int)ceil(($startsTs - time()) / 60)) : 0;
    return [
        'enabled' => $enabled,
        'active' => $active,
        'scheduled' => $scheduled,
        'starts_at' => $startsAt ?: null,
        'minutes_left' => $minutesLeft,
        'message' => $message,
    ];
}

function enforce_maintenance_for_user(PDO $pdo, array $user): void
{
    $state = maintenance_state($pdo);
    if ($state['active'] && !is_superadmin($user)) {
        json_response(['success' => false, 'error' => $state['message'], 'maintenance' => $state], 503);
    }
}

function backup_base_dir(): string
{
    $candidate = dirname(__DIR__) . '/odv_backup/backups';
    if (@is_dir(dirname($candidate)) || @mkdir(dirname($candidate), 0750, true)) {
        return $candidate;
    }
    return __DIR__ . '/backups';
}

function human_size(int $bytes): string
{
    $units = ['B','KB','MB','GB'];
    $size = (float)$bytes;
    $i = 0;
    while ($size >= 1024 && $i < count($units)-1) { $size /= 1024; $i++; }
    return sprintf($i === 0 ? '%.0f %s' : '%.1f %s', $size, $units[$i]);
}

function sql_literal(PDO $pdo, $value): string
{
    if ($value === null) { return 'NULL'; }
    if (is_int($value) || is_float($value)) { return (string)$value; }
    return $pdo->quote((string)$value);
}

function create_pdo_database_backup(PDO $pdo, array $currentUser): array
{
    $dir = backup_base_dir();
    if (!is_dir($dir) && !mkdir($dir, 0750, true) && !is_dir($dir)) {
        json_response(['success' => false, 'error' => 'Backup-Verzeichnis konnte nicht erstellt werden'], 500);
    }
    $date = date('Y-m-d_H-i-s');
    $file = "odv_db_backup_{$date}.sql.gz";
    $path = rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . $file;
    $gz = gzopen($path, 'wb9');
    if (!$gz) {
        json_response(['success' => false, 'error' => 'Backup-Datei konnte nicht geschrieben werden'], 500);
    }
    gzwrite($gz, "-- ODV Datenbanksicherung\n-- Erstellt: " . date('c') . "\n-- Erstellt von: " . ($currentUser['display_name'] ?? '') . "\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n");
    $tables = [];
    foreach ($pdo->query('SHOW TABLES') as $row) {
        $tables[] = array_values($row)[0];
    }
    foreach ($tables as $table) {
        $safe = str_replace('`', '``', (string)$table);
        $create = $pdo->query("SHOW CREATE TABLE `{$safe}`")->fetch(PDO::FETCH_ASSOC);
        $createSql = $create['Create Table'] ?? array_values($create)[1] ?? '';
        gzwrite($gz, "\n-- Tabelle {$table}\nDROP TABLE IF EXISTS `{$safe}`;\n{$createSql};\n\n");
        $stmt = $pdo->query("SELECT * FROM `{$safe}`");
        while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $cols = array_map(fn($c) => '`' . str_replace('`', '``', (string)$c) . '`', array_keys($row));
            $vals = array_map(fn($v) => sql_literal($pdo, $v), array_values($row));
            gzwrite($gz, "INSERT INTO `{$safe}` (" . implode(',', $cols) . ") VALUES (" . implode(',', $vals) . ");\n");
        }
    }
    gzwrite($gz, "\nSET FOREIGN_KEY_CHECKS=1;\n");
    gzclose($gz);
    @chmod($path, 0600);
    $size = filesize($path) ?: 0;
    setting_set($pdo, 'last_backup_file', $file);
    setting_set($pdo, 'last_backup_path', $path);
    setting_set($pdo, 'last_backup_at', date('Y-m-d H:i:s'));
    setting_set($pdo, 'last_backup_size', (string)$size);
    api_log('warning', 'Datenbanksicherung erstellt', ['by_user_id' => $currentUser['id'] ?? null, 'file' => $file, 'size' => $size]);
    return ['file' => $file, 'path' => $path, 'created_at' => date('Y-m-d H:i:s'), 'size' => $size, 'size_human' => human_size((int)$size)];
}

function latest_backup_info(PDO $pdo): array
{
    $file = setting_get($pdo, 'last_backup_file', '');
    $created = setting_get($pdo, 'last_backup_at', '');
    $size = (int)(setting_get($pdo, 'last_backup_size', '0') ?? '0');
    if (!$file) {
        $dir = backup_base_dir();
        $files = glob(rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'odv_db_backup_*.sql.gz') ?: [];
        rsort($files);
        if ($files) {
            $path = $files[0];
            $file = basename($path);
            $created = date('Y-m-d H:i:s', filemtime($path));
            $size = filesize($path) ?: 0;
        }
    }
    if (!$file) { return []; }
    return ['file' => $file, 'created_at' => $created, 'size' => $size, 'size_human' => human_size($size)];
}

function list_database_backups(): array
{
    $dir = backup_base_dir();
    $files = glob(rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'odv_db_backup_*.sql.gz') ?: [];
    rsort($files);
    $items = [];
    foreach ($files as $path) {
        $items[] = [
            'file' => basename($path),
            'created_at' => date('Y-m-d H:i:s', filemtime($path)),
            'size' => filesize($path) ?: 0,
            'size_human' => human_size((int)(filesize($path) ?: 0)),
        ];
    }
    return $items;
}

function database_backup_path_by_file(string $file): string
{
    $file = basename($file);
    if (!preg_match('/^odv_db_backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.sql\.gz$/', $file)) {
        throw new RuntimeException('Ungültiger Backup-Dateiname');
    }
    $path = rtrim(backup_base_dir(), '/\\') . DIRECTORY_SEPARATOR . $file;
    if (!is_file($path)) {
        throw new RuntimeException('Backup-Datei nicht gefunden');
    }
    return $path;
}

function restore_database_backup(PDO $pdo, string $file): array
{
    $path = database_backup_path_by_file($file);
    $gz = gzopen($path, 'rb');
    if (!$gz) {
        throw new RuntimeException('Backup-Datei konnte nicht gelesen werden');
    }
    $statement = '';
    $executed = 0;
    try {
        while (!gzeof($gz)) {
            $line = gzgets($gz);
            if ($line === false) {
                break;
            }
            $trimmed = trim($line);
            if ($trimmed === '' || str_starts_with($trimmed, '--')) {
                continue;
            }
            $statement .= $line;
            if (str_ends_with(rtrim($line), ';')) {
                $sql = trim($statement);
                $statement = '';
                if ($sql !== '') {
                    $pdo->exec($sql);
                    $executed++;
                }
            }
        }
        $rest = trim($statement);
        if ($rest !== '') {
            $pdo->exec($rest);
            $executed++;
        }
    } finally {
        gzclose($gz);
    }
    return [
        'file' => basename($path),
        'statements_executed' => $executed,
        'restored_at' => date('Y-m-d H:i:s'),
    ];
}

function app_update_state(PDO $pdo): array
{
    $version = setting_get($pdo, 'app_update_version', '');
    $fileName = setting_get($pdo, 'app_update_file_name', '');
    $path = setting_get($pdo, 'app_update_nextcloud_relative_path', '');
    $sha256 = setting_get($pdo, 'app_update_sha256', '');
    $required = setting_get($pdo, 'app_update_required', '0') === '1';
    $notes = setting_get($pdo, 'app_update_release_notes', '');
    $publishedAt = setting_get($pdo, 'app_update_published_at', '');
    return [
        'version' => $version,
        'file_name' => $fileName,
        'file' => $fileName,
        'nextcloud_relative_path' => $path,
        'path' => $path,
        'sha256' => $sha256,
        'required' => $required,
        'release_notes' => $notes,
        'published_at' => $publishedAt ?: null,
        'current_api_version' => ODV_API_VERSION,
        'default_update_folder' => '02_AUSTAUSCH/ODV_UPDATE/Windows',
    ];
}

