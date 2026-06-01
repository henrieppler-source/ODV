<?php
declare(strict_types=1);

if ($method === 'POST' && $path === '/api/mails/send') {
    $currentUser = require_role(['admin', 'superadmin']);
    $input = get_json_input();
    $recipients = sanitize_email_list(is_array($input['recipients'] ?? null) ? $input['recipients'] : []);
    $subject = trim((string)($input['subject'] ?? ''));
    $body = (string)($input['body'] ?? '');
    $mode = trim((string)($input['mode'] ?? 'none'));
    if (!in_array($mode, ['none', 'link', 'attachment'], true)) {
        json_response(['success' => false, 'error' => 'Ungültige Versandart'], 400);
    }
    $link = trim((string)($input['link'] ?? ''));
    $shareExpiresAt = trim((string)($input['share_expires_at'] ?? ''));
    $attachments = [];

    if (!$recipients) {
        json_response(['success' => false, 'error' => 'Keine gültigen Empfänger'], 400);
    }
    if ($subject === '') {
        json_response(['success' => false, 'error' => 'Betreff fehlt'], 400);
    }
    if (trim($body) === '') {
        json_response(['success' => false, 'error' => 'Nachrichtentext fehlt'], 400);
    }
    if ($mode === 'link' && $link === '') {
        $localFilePath = trim((string)($input['local_file_path'] ?? ''));
        $localBasePath = trim((string)($input['local_nextcloud_base'] ?? ''));
        if ($localFilePath !== '' && $localBasePath !== '') {
            try {
                $remotePath = build_nextcloud_remote_path($localFilePath, $localBasePath);
                $share = create_nextcloud_public_share($remotePath, $shareExpiresAt);
                $link = $share['download_url'] ?: $share['share_url'];
                $body = str_replace('{link}', $link, $body);
                if (strpos($body, $link) === false) {
                    $body .= "

Downloadlink:
" . $link;
                }
                if ($shareExpiresAt !== '') {
                    $body .= "

Gültig bis:
" . $shareExpiresAt;
                }
            } catch (Throwable $e) {
                api_log('error', 'Nextcloud-Link für Rundmail konnte nicht erzeugt werden', ['error' => $e->getMessage()]);
                json_response(['success' => false, 'error' => 'Nextcloud-Link konnte nicht erzeugt werden: ' . $e->getMessage()], 500);
            }
        }
    }

    if ($mode === 'link' && trim($link) === '' && strpos($body, 'http') === false) {
        json_response(['success' => false, 'error' => 'Für Versandart Link fehlt der Nextcloud-Link'], 400);
    }

    if ($mode === 'attachment') {
        $candidateAttachments = [];
        if (is_array($input['attachments'] ?? null)) {
            $candidateAttachments = $input['attachments'];
        } elseif (is_array($input['attachment'] ?? null)) {
            $candidateAttachments = [$input['attachment']];
        }
        if (!$candidateAttachments) {
            json_response(['success' => false, 'error' => 'Anlage fehlt'], 400);
        }
        $totalSize = 0;
        foreach ($candidateAttachments as $attachment) {
            if (!is_array($attachment) || empty($attachment['content_base64'])) {
                continue;
            }
            $raw = base64_decode((string)$attachment['content_base64'], true);
            if ($raw === false) {
                json_response(['success' => false, 'error' => 'Eine Anlage ist ungültig kodiert'], 400);
            }
            $size = strlen($raw);
            if ($size > 8 * 1024 * 1024) {
                json_response(['success' => false, 'error' => 'Eine Anlage ist größer als 8 MB. Bitte als Link versenden.'], 400);
            }
            $totalSize += $size;
            if ($totalSize > 12 * 1024 * 1024) {
                json_response(['success' => false, 'error' => 'Die Anlagen sind zusammen größer als 12 MB. Bitte als Link versenden.'], 400);
            }
            $attachment['content_base64'] = base64_encode($raw);
            $attachments[] = $attachment;
        }
        if (!$attachments) {
            json_response(['success' => false, 'error' => 'Keine gültige Anlage gefunden'], 400);
        }
    }

    $sent = 0;
    $failed = 0;
    $failedRecipients = [];
    foreach ($recipients as $recipient) {
        $ok = send_text_mail($recipient, $subject, $body, $attachments);
        if ($ok) {
            $sent++;
        } else {
            $failed++;
            $failedRecipients[] = $recipient;
        }
    }
    try {
        $pdo = db();
        ensure_mail_history_table($pdo);
        $docs = [];
        if (is_array($input['documents'] ?? null)) {
            $docs = $input['documents'];
        }
        if ($link !== '') {
            $docInfo = ['link' => $link];
            if ($shareExpiresAt !== '') {
                $docInfo['expires_at'] = $shareExpiresAt;
            }
            $docs[] = $docInfo;
        }
        if ($attachments) {
            foreach ($attachments as $attachment) {
                $docs[] = ['attachment' => (string)($attachment['filename'] ?? 'Anhang')];
            }
        }
        $hist = $pdo->prepare("INSERT INTO mail_history (sent_by_user_id, sent_by_name, recipient_email, subject, body_preview, mode, status, error_message, documents_json) VALUES (:uid, :uname, :recipient, :subject, :body_preview, :mode, :status, :error_message, :documents_json)");
        foreach ($recipients as $recipient) {
            $isFailed = in_array($recipient, $failedRecipients, true);
            $hist->execute([
                ':uid' => $currentUser['id'],
                ':uname' => $currentUser['display_name'],
                ':recipient' => $recipient,
                ':subject' => $subject,
                ':body_preview' => (function_exists('mb_substr') ? mb_substr($body, 0, 1000) : substr($body, 0, 1000)),
                ':mode' => $mode,
                ':status' => $isFailed ? 'failed' : 'sent',
                ':error_message' => $isFailed ? 'mail() fehlgeschlagen' : null,
                ':documents_json' => json_encode($docs, JSON_UNESCAPED_UNICODE),
            ]);
        }
    } catch (Throwable $e) {
        api_log('warning', 'Mail-Historie konnte nicht geschrieben werden', ['error' => $e->getMessage()]);
    }

    api_log($failed > 0 ? 'warning' : 'info', 'Rundmail versendet', [
        'by_user_id' => $currentUser['id'],
        'recipient_count' => count($recipients),
        'sent' => $sent,
        'failed' => $failed,
        'mode' => $mode,
        'share_expires_at' => $shareExpiresAt,
        'attachment_count' => count($attachments),
        'subject' => $subject,
    ]);
    json_response([
        'success' => $sent > 0,
        'message' => 'Rundmail-Versand abgeschlossen',
        'sent' => $sent,
        'failed' => $failed,
        'failed_recipients' => $failedRecipients,
    ], $sent > 0 ? 200 : 500);
}

if ($method === 'GET' && $path === '/api/mails/history') {
    $currentUser = require_role(['admin', 'superadmin']);
    $limit = max(1, min(1000, (int)($_GET['limit'] ?? 200)));
    $pdo = db();
    ensure_mail_history_table($pdo);
    $stmt = $pdo->prepare("SELECT id, sent_at, sent_by_user_id, sent_by_name AS sender_name, recipient_email, subject, body_preview, mode, status, error_message, documents_json FROM mail_history ORDER BY sent_at DESC, id DESC LIMIT " . $limit);
    $stmt->execute();
    $items = [];
    foreach ($stmt->fetchAll() as $row) {
        $docs = [];
        if (!empty($row['documents_json'])) {
            $decoded = json_decode((string)$row['documents_json'], true);
            if (is_array($decoded)) { $docs = $decoded; }
        }
        $row['documents'] = $docs;
        unset($row['documents_json']);
        $items[] = $row;
    }
    json_response(['success' => true, 'items' => $items]);
}

if ($method === 'POST' && $path === '/api/nextcloud/share') {
    $currentUser = current_user();
    $input = get_json_input();
    $localFilePath = trim((string)($input['local_file_path'] ?? ''));
    $localBasePath = trim((string)($input['local_nextcloud_base'] ?? ''));
    $shareExpiresAt = trim((string)($input['share_expires_at'] ?? ''));
    if ($localFilePath === '' || $localBasePath === '') {
        json_response(['success' => false, 'error' => 'local_file_path und local_nextcloud_base sind erforderlich'], 400);
    }
    $remotePath = build_nextcloud_remote_path($localFilePath, $localBasePath);
    $share = create_nextcloud_public_share($remotePath, $shareExpiresAt);
    api_log('info', 'Nextcloud-Freigabe-Link erzeugt', [
        'by_user_id' => $currentUser['id'],
        'local_file_path' => $localFilePath,
        'local_nextcloud_base' => $localBasePath,
        'share_expires_at' => $shareExpiresAt,
    ]);
    json_response([
        'success' => true,
        'remote_path' => $remotePath,
        'download_url' => $share['download_url'] ?? '',
        'share_url' => $share['share_url'] ?? '',
        'url' => $share['url'] ?? '',
        'share_expires_at' => $shareExpiresAt,
    ]);
}
