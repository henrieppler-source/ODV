<?php

declare(strict_types=1);


if (!function_exists('current_points_year')) {


function current_points_year(): int

{

    return (int)date('Y');

}



function ensure_point_year_closures_table(PDO $pdo): void

{

    $pdo->exec("CREATE TABLE IF NOT EXISTS point_year_closures (

        year INT PRIMARY KEY,

        closed_at DATETIME DEFAULT NULL,

        closed_by_user_id INT DEFAULT NULL,

        note TEXT DEFAULT NULL,

        CONSTRAINT fk_point_year_closed_by FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL

    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

}



function points_year_budget_key(int $year): string

{

    return 'points_year_budget_' . $year;

}



function point_year_closure(PDO $pdo, int $year): ?array

{

    ensure_point_year_closures_table($pdo);

    $stmt = $pdo->prepare("
        SELECT pyc.year, pyc.closed_at, pyc.closed_by_user_id, pyc.note, u.display_name AS closed_by_name
        FROM point_year_closures pyc
        LEFT JOIN users u ON u.id = pyc.closed_by_user_id
        WHERE pyc.year = :year
        LIMIT 1
    ");

    $stmt->execute([':year' => $year]);

    $row = $stmt->fetch();

    return $row ?: null;

}



function point_year_is_closed(PDO $pdo, int $year): bool

{

    return point_year_closure($pdo, $year) !== null;

}



function points_year_budget(PDO $pdo, int $year): float

{

    $value = setting_get($pdo, points_year_budget_key($year), null);

    if ($value === null || trim($value) === '') {

        return 0.0;

    }

    return (float)str_replace(',', '.', (string)$value);

}



function points_year_total(PDO $pdo, int $year): array

{

    $stmt = $pdo->prepare("
        SELECT
            COALESCE(SUM(cp.points), 0) AS total_points,
            COUNT(DISTINCT cp.user_id) AS participant_count
        FROM contribution_points cp
        LEFT JOIN documents d ON d.id = cp.document_id
        WHERE cp.points_year = :year
          AND cp.is_confirmed = 1
          AND (d.status IN ('erfasst', 'geprueft', 'archiviert') OR cp.is_manual = 1)
    ");

    $stmt->execute([':year' => $year]);

    $row = $stmt->fetch();

    return [

        'total_points' => (int)($row['total_points'] ?? 0),

        'participant_count' => (int)($row['participant_count'] ?? 0),

    ];

}



function require_points_year_editable(PDO $pdo, int $year): void

{

    if (point_year_is_closed($pdo, $year)) {

        json_response(['success' => false, 'error' => 'Das Punktejahr ist abgeschlossen und kann nicht mehr geändert werden.'], 409);

    }

}

}
