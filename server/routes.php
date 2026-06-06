<?php
declare(strict_types=1);

require_once __DIR__ . '/database.php';

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$method = $_SERVER['REQUEST_METHOD'];
$path = rtrim($path, '/');

const ODV_API_VERSION = 'v121';

require_once __DIR__ . '/routes_shared.php';

require_once __DIR__ . '/routes_auth.php';

require_once __DIR__ . '/routes_user_admin.php';

require_once __DIR__ . '/routes_documents.php';

require_once __DIR__ . '/routes_mail.php';

require_once __DIR__ . '/routes_admin_endpoints.php';
require_once __DIR__ . '/routes_points.php';
require_once __DIR__ . '/routes_mail_groups.php';

json_response([
    'success' => false,
    'error' => 'Route nicht gefunden',
    'path' => $path
], 404);
