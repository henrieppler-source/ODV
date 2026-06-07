<?php

declare(strict_types=1);

function build_nextcloud_remote_path(string $localFilePath, string $localNextcloudBase): string

{

    $file = trim(str_replace('\\', '/', $localFilePath));

    $base = trim(str_replace('\\', '/', $localNextcloudBase));

    if ($file === '') {

        return '';

    }

    if ($base !== '' && str_starts_with($file, $base)) {

        $relative = ltrim(substr($file, strlen($base)), '/');

        return $relative;

    }

    return ltrim($file, '/');

}



function normalize_folder_token_api(string $value): string

{

    $text = mb_strtolower(trim($value), 'UTF-8');

    $text = str_replace(['ä', 'ö', 'ü', 'ß'], ['ae', 'oe', 'ue', 'ss'], $text);

    $text = preg_replace('/[^a-z0-9]+/u', '_', $text) ?? $text;

    return trim($text, '_');

}



function top_folder_from_path(string $path): string

{

    $path = str_replace('\\', '/', trim($path));

    if ($path === '') { return ''; }

    $parts = array_values(array_filter(explode('/', $path), static fn($p) => $p !== '' && $p !== '.'));

    foreach ($parts as $part) {

        if (preg_match('/^\d{2}_.+/', $part)) {

            return $part;

        }

    }

    return $parts[0] ?? '';

}



function load_place_folder_map(PDO $pdo): array

{

    $map = [];

    try {

        $rows = $pdo->query("SELECT place, folder_name FROM place_folders WHERE is_active = 1")->fetchAll();

        foreach ($rows as $row) {

            $map[normalize_folder_token_api((string)$row['place'])] = (string)$row['folder_name'];

        }

    } catch (Throwable $e) {

        // Migration fehlt evtl. noch; dann ohne Stammdaten fortfahren.

    }

    return $map;

}



function folder_group_from_path(PDO $pdo, array $user, string $path): ?string

{

    $top = top_folder_from_path($path);

    $topNorm = normalize_folder_token_api($top);

    $fixed = ['00_ORTSCHRONIK', '01_ABLAGE_ORTSCHRONIK', '02_AUSTAUSCH', '03_INFORMATION', '05_ORGA_CHRONISTEN', '06_UNSERE_ARBEITEN'];

    foreach ($fixed as $name) {

        if ($topNorm === normalize_folder_token_api($name)) {

            return $name;

        }

    }

    $placeNorm = normalize_folder_token_api((string)($user['place'] ?? ''));

    $placeFolders = load_place_folder_map($pdo);

    $ownFolder = $placeFolders[$placeNorm] ?? '';

    if ($ownFolder !== '' && $topNorm === normalize_folder_token_api($ownFolder)) {

        return 'OWN_PLACE_FOLDER';

    }

    if ($placeNorm !== '' && strpos($topNorm, $placeNorm) !== false) {

        return 'OWN_PLACE_FOLDER';

    }

    $known = array_map('normalize_folder_token_api', array_values($placeFolders));

    if (in_array($topNorm, $known, true)) {

        return 'OTHER_PLACE_FOLDERS';

    }

    if (preg_match('/^\d{2}_.+/', $top)) {

        return 'OTHER_PLACE_FOLDERS';

    }

    return null;

}

