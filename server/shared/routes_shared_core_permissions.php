<?php

declare(strict_types=1);

function folder_groups(): array

{

    return [

        '00_ORTSCHRONIK' => '00_ORTSCHRONIK',

        '01_ABLAGE_ORTSCHRONIK' => '01_ABLAGE_ORTSCHRONIK',

        '02_AUSTAUSCH' => '02_AUSTAUSCH',

        '03_INFORMATION' => '03_INFORMATION',

        '05_ORGA_CHRONISTEN' => '05_ORGA_CHRONISTEN',

        '06_UNSERE_ARBEITEN' => '06_UNSERE_ARBEITEN',

        'OWN_PLACE_FOLDER' => 'Eigener Ortsordner',

        'OTHER_PLACE_FOLDERS' => 'Andere Ortsordner',

    ];

}

function default_folder_permissions(string $role): array

{

    $role = strtolower($role);

    $all = [];

    foreach (array_keys(folder_groups()) as $key) {

        $all[$key] = ['can_read' => 1, 'can_write' => 1];

    }

    if (in_array($role, ['admin', 'superadmin'], true)) {

        return $all;

    }

    return [

        '00_ORTSCHRONIK' => ['can_read' => 1, 'can_write' => 0],

        '01_ABLAGE_ORTSCHRONIK' => ['can_read' => 1, 'can_write' => 1],

        '02_AUSTAUSCH' => ['can_read' => 1, 'can_write' => 1],

        '03_INFORMATION' => ['can_read' => 1, 'can_write' => 0],

        '05_ORGA_CHRONISTEN' => ['can_read' => 0, 'can_write' => 0],

        '06_UNSERE_ARBEITEN' => ['can_read' => 1, 'can_write' => 1],

        'OWN_PLACE_FOLDER' => ['can_read' => 1, 'can_write' => 1],

        'OTHER_PLACE_FOLDERS' => ['can_read' => 0, 'can_write' => 0],

    ];

}

function fetch_user_folder_permissions(PDO $pdo, int $userId, string $role): array

{

    $defaults = default_folder_permissions(strtolower(trim($role)));

    $stmt = $pdo->prepare("SELECT folder_group, can_read, can_write FROM user_folder_permissions WHERE user_id = :user_id");

    $stmt->execute([':user_id' => $userId]);

    foreach ($stmt->fetchAll() as $row) {

        $key = (string)$row['folder_group'];

        if (isset($defaults[$key])) {

            $defaults[$key] = ['can_read' => (int)$row['can_read'], 'can_write' => (int)$row['can_write']];

        }

    }

    $out = [];

    foreach (folder_groups() as $key => $label) {

        $out[] = [

            'folder_group' => $key,

            'label' => $label,

            'can_read' => (int)$defaults[$key]['can_read'],

            'can_write' => (int)$defaults[$key]['can_write'],

        ];

    }

    return $out;

}
