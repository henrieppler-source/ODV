<?php

declare(strict_types=1);


if (!function_exists('point_rule_points')) {


function point_rule_points(PDO $pdo, int $year, string $ruleKey, int $default = 0): int

{

    $stmt = $pdo->prepare("SELECT points FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");

    $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);

    $row = $stmt->fetch();

    return $row ? (int)$row['points'] : $default;

}



function point_rule_key_for_field_category(PDO $pdo, int $year, string $field, string $category, string $fallback): string

{

    $candidates = [$field . '_' . $category];

    if ($category === 'metadata') {

        $candidates[] = $field . '_metadaten';

    }

    $candidates[] = $fallback;

    foreach (array_values(array_unique($candidates)) as $ruleKey) {

        $stmt = $pdo->prepare("SELECT rule_key FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");

        $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);

        $row = $stmt->fetch();

        if ($row) {

            return (string)$row['rule_key'];

        }

    }

    return $fallback;

}



function metadata_point_rule_catalog(): array

{

    return [

        'description' => ['label' => 'Aussagekräftige Beschreibung', 'check_type' => 'characters', 'min_value' => 50],

        'keywords' => ['label' => 'Stichwörter vergeben', 'check_type' => 'count', 'min_value' => 3],

        'source' => ['label' => 'Quelle/Herkunft angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'usage_permission' => ['label' => 'Nutzungsfreigabe geklärt', 'check_type' => 'characters', 'min_value' => 3],

        'rights_note' => ['label' => 'Rechtehinweis angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'copyright_author' => ['label' => 'Urheber angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'rights_holder' => ['label' => 'Rechteinhaber angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'archive_name' => ['label' => 'Archiv/Bestand angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'archive_signature' => ['label' => 'Archivsignatur angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'document_date' => ['label' => 'Datum/Zeitraum angegeben', 'check_type' => 'characters', 'min_value' => 3],

        'event' => ['label' => 'Ereignis/Thema zugeordnet', 'check_type' => 'characters', 'min_value' => 3],

    ];

}



function metadata_point_rule_key(string $field, string $source): string

{

    return trim($field) . '_' . ($source === 'openAI' ? 'openAI' : 'manual');

}



function point_rule_config(PDO $pdo, int $year, string $ruleKey): ?array

{

    $stmt = $pdo->prepare("SELECT * FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");

    $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);

    $row = $stmt->fetch();

    return $row ?: null;

}

}
