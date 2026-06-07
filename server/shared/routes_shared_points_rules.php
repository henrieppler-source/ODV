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


function point_rule_source_field_from_key(string $ruleKey): string

{

    $key = trim($ruleKey);
    if ($key === '') {
        return 'manual_bonus';
    }
    foreach (['_metadata', '_metadaten', '_manual', '_openAI'] as $suffix) {
        if (str_ends_with($key, $suffix)) {
            $key = substr($key, 0, -strlen($suffix));
            break;
        }
    }
    $aliases = [
        'metadata_description' => 'description',
        'metadata_keywords' => 'keywords',
        'metadata_source' => 'source',
        'rights_author' => 'copyright_author',
        'rights_usage_permission' => 'usage_permission',
        'rights_note' => 'rights_note',
        'archive_name' => 'archive_name',
        'archive_signature' => 'archive_signature',
        'document_date' => 'document_date',
        'event' => 'event',
        'event_topic' => 'event',
        'openai_metadata' => 'openai_metadata',
        'persons_image_marked' => 'persons',
        'persons_per_person' => 'persons',
        'metadata_correction' => 'manual_bonus',
        'admin_review_accepted' => 'status',
        'admin_file_organization' => 'status',
        'special_collection' => 'current_path',
        'transcription_short' => 'transcription_done',
        'transcription_full' => 'transcription_done',
        'transcription_document' => 'transcription_done',
        'transcription_difficult' => 'transcription_done',
    ];
    return $aliases[$key] ?? $key;

}


function valid_point_rules_catalog(): array

{

    $catalog = [];
    $metadataRules = metadata_point_rule_catalog();
    $metadataSourceFields = [
        'description' => 'description',
        'keywords' => 'keywords',
        'source' => 'source',
        'usage_permission' => 'usage_permission',
        'rights_note' => 'rights_note',
        'copyright_author' => 'copyright_author',
        'rights_holder' => 'rights_holder',
        'archive_name' => 'archive_name',
        'archive_signature' => 'archive_signature',
        'document_date' => 'document_date',
        'event' => 'event',
    ];

    $catalog[] = [
        'rule_key' => 'admin_file_organization',
        'label' => 'Datei umbenannt oder verschoben',
        'category' => 'admin_review',
        'rule_type' => 'admin_review',
        'source_field' => 'status',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 1,
        'is_active' => 1,
        'is_system' => 1,
    ];

    foreach ($metadataRules as $field => $info) {
        $sourceField = $metadataSourceFields[$field] ?? $field;
        $catalog[] = [
            'rule_key' => 'metadata_' . $field,
            'label' => (string)$info['label'],
            'category' => 'metadata',
            'rule_type' => 'metadata',
            'source_field' => $sourceField,
            'evaluation_source' => '',
            'check_type' => (string)$info['check_type'],
            'min_value' => (int)$info['min_value'],
            'points' => 1,
            'is_active' => 1,
            'is_system' => 1,
        ];
        $catalog[] = [
            'rule_key' => metadata_point_rule_key($field, 'openAI'),
            'label' => (string)$info['label'],
            'category' => 'metadata',
            'rule_type' => 'metadata',
            'source_field' => $sourceField,
            'evaluation_source' => 'openAI',
            'check_type' => (string)$info['check_type'],
            'min_value' => (int)$info['min_value'],
            'points' => 1,
            'is_active' => 1,
            'is_system' => 1,
        ];
        $catalog[] = [
            'rule_key' => metadata_point_rule_key($field, 'manual'),
            'label' => (string)$info['label'],
            'category' => 'metadata',
            'rule_type' => 'metadata',
            'source_field' => $sourceField,
            'evaluation_source' => 'manual',
            'check_type' => (string)$info['check_type'],
            'min_value' => (int)$info['min_value'],
            'points' => 2,
            'is_active' => 1,
            'is_system' => 1,
        ];
        $catalog[] = [
            'rule_key' => 'metadata_correction_' . $field,
            'label' => (string)$info['label'] . ' (Korrektur/Ergänzung)',
            'category' => 'metadata',
            'rule_type' => 'metadata',
            'source_field' => $sourceField . '_correction',
            'evaluation_source' => 'manual',
            'check_type' => 'characters',
            'min_value' => 1,
            'points' => 1,
            'is_active' => 1,
            'is_system' => 1,
        ];
    }

    $catalog[] = [
        'rule_key' => 'metadata_correction',
        'label' => 'Fachliche Korrektur oder Ergänzung',
        'category' => 'metadata',
        'rule_type' => 'metadata',
        'source_field' => 'manual_bonus',
        'evaluation_source' => 'manual',
        'check_type' => 'characters',
        'min_value' => 1,
        'points' => 1,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'transcription_short',
        'label' => 'Transkription / Abschrift erstellt',
        'category' => 'metadata',
        'rule_type' => 'metadata',
        'source_field' => 'transcription_done',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 3,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'transcription_full',
        'label' => 'Vollständige Transkription',
        'category' => 'metadata',
        'rule_type' => 'metadata',
        'source_field' => 'transcription_done',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 5,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'transcription_difficult',
        'label' => 'Schwierige Transkription',
        'category' => 'metadata',
        'rule_type' => 'metadata',
        'source_field' => 'transcription_done',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 8,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'transcription_document',
        'label' => 'Transkription Zeitung / Akte / Urkunde',
        'category' => 'metadata',
        'rule_type' => 'metadata',
        'source_field' => 'transcription_done',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 10,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'persons_image_marked',
        'label' => 'Bild mit Personenmarkierungen',
        'category' => 'persons',
        'rule_type' => 'persons',
        'source_field' => 'persons',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 5,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'persons_per_person',
        'label' => 'Personenmarkierung je Person',
        'category' => 'persons',
        'rule_type' => 'persons',
        'source_field' => 'person',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 1,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'admin_review_accepted',
        'label' => 'Dokument geprüft und übernommen',
        'category' => 'admin_review',
        'rule_type' => 'admin_review',
        'source_field' => 'status',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 1,
        'is_active' => 1,
        'is_system' => 1,
    ];

    $catalog[] = [
        'rule_key' => 'special_collection',
        'label' => 'Sonder-Sammlung gepflegt',
        'category' => 'special_collection',
        'rule_type' => 'special_collection',
        'source_field' => 'current_path',
        'evaluation_source' => 'manual',
        'check_type' => 'none',
        'min_value' => 0,
        'points' => 10,
        'is_active' => 1,
        'is_system' => 1,
    ];

    return $catalog;

}


function point_rule_config(PDO $pdo, int $year, string $ruleKey): ?array

{

    $stmt = $pdo->prepare("SELECT * FROM point_rules WHERE year = :year AND rule_key = :rule_key AND is_active = 1 LIMIT 1");

    $stmt->execute([':year' => $year, ':rule_key' => $ruleKey]);

    $row = $stmt->fetch();

    return $row ?: null;

}

}
