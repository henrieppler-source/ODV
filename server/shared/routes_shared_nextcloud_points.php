<?php

declare(strict_types=1);

function document_person_events_from_payload(array $document, array $persons): array

{

    $events = [];

    foreach ($persons as $person) {

        if (!is_array($person)) {

            continue;

        }

        $number = (int)($person['number'] ?? 0);

        $displayName = trim((string)($person['display_name'] ?? ''));

        if ($number <= 0 || $displayName === '') {

            continue;

        }

        $events[] = [

            'number' => $number,

            'display_name' => $displayName,

            'x' => isset($person['x']) ? (float)$person['x'] : null,

            'y' => isset($person['y']) ? (float)$person['y'] : null,

            'certainty' => isset($person['certainty']) ? (float)$person['certainty'] : null,

            'note' => trim((string)($person['note'] ?? '')),

        ];

    }

    return $events;

}



function add_person_points_for_document(PDO $pdo, int $documentId, string $uploadId, array $user, array $document, array $events): void

{

    add_person_points($pdo, $documentId, $uploadId, $user, $events);

}

