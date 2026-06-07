<?php

declare(strict_types=1);


if (!function_exists('db_table_exists')) {


function db_table_exists(PDO $pdo, string $tableName): bool

{

    static $cache = [];

    $key = strtolower($tableName);

    if (array_key_exists($key, $cache)) {

        return $cache[$key];

    }

    try {

        $stmt = $pdo->prepare("SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name");

        $stmt->execute([':table_name' => $tableName]);

        $cache[$key] = ((int)$stmt->fetchColumn()) > 0;

    } catch (Throwable $e) {

        $cache[$key] = false;

    }

    return $cache[$key];

}



function db_column_exists(PDO $pdo, string $tableName, string $columnName): bool

{

    static $cache = [];

    $key = strtolower($tableName . '.' . $columnName);

    if (array_key_exists($key, $cache)) {

        return $cache[$key];

    }

    try {

        $stmt = $pdo->prepare("SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name AND COLUMN_NAME = :column_name");

        $stmt->execute([':table_name' => $tableName, ':column_name' => $columnName]);

        $cache[$key] = ((int)$stmt->fetchColumn()) > 0;

    } catch (Throwable $e) {

        $cache[$key] = false;

    }

    return $cache[$key];

}



function quote_identifier(string $name): string

{

    return '`' . str_replace('`', '``', $name) . '`';

}



function backup_table_for_version(PDO $pdo, string $tableName, string $fromVersion): ?string

{

    if (!db_table_exists($pdo, $tableName)) {

        return null;

    }

    $suffix = preg_replace('/[^A-Za-z0-9_]/', '', $fromVersion);

    $backupName = $tableName . '_' . $suffix;

    if (db_table_exists($pdo, $backupName)) {

        return $backupName;

    }

    $source = quote_identifier($tableName);

    $target = quote_identifier($backupName);

    $pdo->exec("CREATE TABLE {$target} LIKE {$source}");

    $pdo->exec("INSERT INTO {$target} SELECT * FROM {$source}");

    return $backupName;

}



function ensure_schema_migrations_table(PDO $pdo): void

{

    $pdo->exec("CREATE TABLE IF NOT EXISTS odv_schema_migrations (

        id INT AUTO_INCREMENT PRIMARY KEY,

        migration_key VARCHAR(100) NOT NULL,

        from_version VARCHAR(20) NOT NULL,

        to_version VARCHAR(20) NOT NULL,

        description TEXT DEFAULT NULL,

        backup_tables TEXT DEFAULT NULL,

        executed_by_user_id INT DEFAULT NULL,

        executed_by_name VARCHAR(255) DEFAULT NULL,

        executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        UNIQUE KEY uniq_migration_key (migration_key),

        INDEX idx_schema_migrations_executed_at (executed_at)

    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

}



function schema_migration_done(PDO $pdo, string $key): bool

{

    if (!db_table_exists($pdo, 'odv_schema_migrations')) {

        return false;

    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM odv_schema_migrations WHERE migration_key = :k");

    $stmt->execute([':k' => $key]);

    return ((int)$stmt->fetchColumn()) > 0;

}



function record_schema_migration(PDO $pdo, string $key, string $fromVersion, string $toVersion, string $description, array $backupTables, array $currentUser): void

{

    ensure_schema_migrations_table($pdo);

    $stmt = $pdo->prepare("INSERT IGNORE INTO odv_schema_migrations

        (migration_key, from_version, to_version, description, backup_tables, executed_by_user_id, executed_by_name)

        VALUES (:migration_key, :from_version, :to_version, :description, :backup_tables, :executed_by_user_id, :executed_by_name)");

    $stmt->execute([

        ':migration_key' => $key,

        ':from_version' => $fromVersion,

        ':to_version' => $toVersion,

        ':description' => $description,

        ':backup_tables' => implode(',', $backupTables),

        ':executed_by_user_id' => (int)($currentUser['id'] ?? 0),

        ':executed_by_name' => (string)($currentUser['display_name'] ?? ''),

    ]);

}



function available_schema_migrations(PDO $pdo): array

{

    return [

        [

            'key' => 'v106_schema_migration_framework',

            'from_version' => 'v105',

            'to_version' => 'v106',

            'description' => 'Migrationsprotokoll fuer kuenftige serverseitige Datenbankanpassungen anlegen.',

            'pending' => !schema_migration_done($pdo, 'v106_schema_migration_framework'),

            'backup_tables' => [],

        ],

        [

            'key' => 'v111_point_rules_optimization',

            'from_version' => 'v110',

            'to_version' => 'v111',

            'description' => 'Punkteregeln auf Metadatenfeld/Wertung, Mindestpruefung, Sonderregeln und manuelle Zusatzpunkte umstellen.',

            'pending' => !schema_migration_done($pdo, 'v111_point_rules_optimization'),

            'backup_tables' => ['point_rules_v110'],

        ],

    ];

}



function apply_schema_migrations(PDO $pdo, array $currentUser): array

{

    $applied = [];

    ensure_schema_migrations_table($pdo);

    if (!schema_migration_done($pdo, 'v106_schema_migration_framework')) {

        record_schema_migration(

            $pdo,

            'v106_schema_migration_framework',

            'v105',

            'v106',

            'Migrationsprotokoll fuer kuenftige serverseitige Datenbankanpassungen angelegt.',

            [],

            $currentUser

        );

        $applied[] = 'v106_schema_migration_framework';

    }

    if (!schema_migration_done($pdo, 'v111_point_rules_optimization')) {

        $backupTables = [];

        $backup = backup_table_for_version($pdo, 'point_rules', 'v110');

        if ($backup) { $backupTables[] = $backup; }

        ensure_point_rules_model_columns($pdo);

        $year = current_points_year();

        $stmt = $pdo->prepare("INSERT INTO point_rules (year, rule_key, label, category, rule_type, source_field, evaluation_source, check_type, min_value, points, is_active, is_system, updated_by_user_id)

            VALUES (:year, :rule_key, :label, :category, :rule_type, :source_field, :evaluation_source, :check_type, :min_value, :points, 1, :is_system, :updated_by_user_id)

            ON DUPLICATE KEY UPDATE label = VALUES(label), category = VALUES(category), rule_type = VALUES(rule_type), source_field = VALUES(source_field), evaluation_source = VALUES(evaluation_source), check_type = VALUES(check_type), min_value = VALUES(min_value), points = VALUES(points), is_active = 1, is_system = VALUES(is_system), updated_by_user_id = VALUES(updated_by_user_id)");

        $keptKeys = [];

        foreach (valid_point_rules_catalog() as $rule) {

            $keptKeys[] = $rule['rule_key'];

            $stmt->execute([

                ':year' => $year,

                ':rule_key' => $rule['rule_key'],

                ':label' => $rule['label'],

                ':category' => $rule['category'],

                ':rule_type' => $rule['rule_type'],

                ':source_field' => $rule['source_field'],

                ':evaluation_source' => $rule['evaluation_source'],

                ':check_type' => $rule['check_type'],

                ':min_value' => (int)($rule['min_value'] ?? 0),

                ':points' => (int)($rule['points'] ?? 0),

                ':is_system' => (int)($rule['is_system'] ?? 0),

                ':updated_by_user_id' => (int)($currentUser['id'] ?? 0),

            ]);

        }

        if ($keptKeys) {

            $placeholders = implode(',', array_fill(0, count($keptKeys), '?'));

            $deleteStmt = $pdo->prepare("DELETE FROM point_rules WHERE year = ? AND rule_key NOT IN ($placeholders)");

            $deleteStmt->execute(array_merge([$year], $keptKeys));

        }

        record_schema_migration(

            $pdo,

            'v111_point_rules_optimization',

            'v110',

            'v111',

            'Punkteregeln auf Metadatenfeld/Wertung, Mindestpruefung, Sonderregeln und manuelle Zusatzpunkte umgestellt.',

            $backupTables,

            $currentUser

        );

        $applied[] = 'v111_point_rules_optimization';

    }

    return $applied;

}

}
