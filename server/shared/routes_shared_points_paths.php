<?php

declare(strict_types=1);


if (!function_exists('normalize_point_path')) {


function normalize_point_path(string $path): string

{

    return strtolower(str_replace('\\', '/', $path));

}



function is_point_eligible_path(string $path): bool

{

    $path = '/' . trim(normalize_point_path($path), '/') . '/';

    if ($path === '//') { return false; }

    $eligible = [

        '00_ortschronik',

        '01_ablage_ortschronik',

        '06_unsere_arbeiten',

        '06_arbeit_der_ortschronisten',

        '06_arbeiten_der_ortschronisten'

    ];

    foreach ($eligible as $folder) {

        if (str_contains($path, '/' . $folder . '/')) { return true; }

    }

    return false;

}



function normalized_path_words(string $path): string

{

    $text = normalize_point_path($path);

    $text = str_replace(['ä', 'ö', 'ü', 'ß'], ['ae', 'oe', 'ue', 'ss'], $text);

    $text = preg_replace('/[^a-z0-9]+/u', ' ', $text) ?? $text;

    return trim($text);

}



function special_collection_for_document_path(string $targetFolder, string $currentPath): ?string

{

    $haystack = normalized_path_words($targetFolder . ' ' . $currentPath);

    if (str_contains($haystack, 'kinder wie die zeit vergeht')) {

        return 'kinder_wie_die_zeit_vergeht';

    }

    if (str_contains($haystack, 'jahresblatt') || str_contains($haystack, 'jahresblaetter')) {

        return 'jahresblaetter';

    }

    return null;

}

}
