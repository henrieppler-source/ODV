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

}
