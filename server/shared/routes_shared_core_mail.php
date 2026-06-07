<?php

declare(strict_types=1);

function send_text_mail(string $to, string $subject, string $body, array $attachments = [], string $replyTo = '', string $bodyHtml = ''): bool

{

    $recipient = trim($to);

    if ($recipient === '') {

        return false;

    }

    if (function_exists('mb_encode_mimeheader')) {

        $encodedSubject = mb_encode_mimeheader($subject, 'UTF-8', 'Q', "\r\n");

    } else {

        $encodedSubject = '=?UTF-8?B?' . base64_encode($subject) . '?=';

    }

    $headers = [

        'MIME-Version: 1.0',

        'From: Ortschronik <info@ortschronik.info>',

    ];

    $replyTo = trim($replyTo);

    if ($replyTo !== '' && filter_var($replyTo, FILTER_VALIDATE_EMAIL)) {

        $headers[] = 'Reply-To: ' . $replyTo;

    }

    $cleanAttachments = [];

    foreach ($attachments as $attachment) {

        if (!is_array($attachment) || empty($attachment['content_base64'])) {

            continue;

        }

        $cleanAttachments[] = $attachment;

    }

    $hasHtml = trim($bodyHtml) !== '';

    $params = '-f info@ortschronik.info';

    $sendPlainFallback = static function (string $recipient, string $encodedSubject, string $body, array $headers, string $params): bool {

        $plainHeaders = [];

        foreach ($headers as $header) {

            if (stripos($header, 'Content-Type:') === 0 || stripos($header, 'Content-Transfer-Encoding:') === 0) {

                continue;

            }

            $plainHeaders[] = $header;

        }

        $plainHeaders[] = "Content-Type: text/plain; charset=UTF-8";

        $plainHeaders[] = "Content-Transfer-Encoding: 8bit";

        return mail($recipient, $encodedSubject, $body, implode("\r\n", $plainHeaders), $params);

    };

    if ($cleanAttachments) {

        $boundaryMixed = '=_odv_mixed_' . bin2hex(random_bytes(12));

        $buildMixedMessage = static function (bool $includeHtml) use ($boundaryMixed, $body, $bodyHtml, $cleanAttachments): string {

            $message = "This is a multi-part message in MIME format.\r\n";

            $message .= "--{$boundaryMixed}\r\n";

            if ($includeHtml) {

                $boundaryAlt = '=_odv_alt_' . bin2hex(random_bytes(12));

                $message .= "Content-Type: multipart/alternative; boundary=\"{$boundaryAlt}\"\r\n\r\n";

                $message .= "--{$boundaryAlt}\r\n";

                $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $body . "\r\n";

                $message .= "--{$boundaryAlt}\r\n";

                $message .= "Content-Type: text/html; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $bodyHtml . "\r\n";

                $message .= "--{$boundaryAlt}--\r\n";

            } else {

                $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

                $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

                $message .= $body . "\r\n";

            }

            foreach ($cleanAttachments as $attachment) {

                $filename = trim((string)($attachment['filename'] ?? 'Anhang'));

                $mime = trim((string)($attachment['mime_type'] ?? 'application/octet-stream'));

                $raw = base64_decode((string)$attachment['content_base64'], true);

                if ($raw === false) {

                    continue;

                }

                $message .= "--{$boundaryMixed}\r\n";

                $message .= "Content-Type: {$mime}; name=\"" . str_replace('"', '\\"', $filename) . "\"\r\n";

                $message .= "Content-Transfer-Encoding: base64\r\n";

                $message .= "Content-Disposition: attachment; filename=\"" . str_replace('"', '\\"', $filename) . "\"\r\n\r\n";

                $message .= chunk_split(base64_encode($raw)) . "\r\n";

            }

            $message .= "--{$boundaryMixed}--\r\n";

            return $message;

        };

        $headersMixed = $headers;

        $headersMixed[] = "Content-Type: multipart/mixed; boundary=\"{$boundaryMixed}\"";

        $message = $buildMixedMessage($hasHtml);

        $sent = mail($recipient, $encodedSubject, $message, implode("\r\n", $headersMixed), $params);

        if (!$sent && $hasHtml) {

            $messageFallback = $buildMixedMessage(false);

            $sent = mail($recipient, $encodedSubject, $messageFallback, implode("\r\n", $headersMixed), $params);

        }

        if (!$sent) {

            $sent = $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

        }

        return $sent;

    }

    if ($hasHtml) {

        $boundary = '=_odv_alt_' . bin2hex(random_bytes(12));

        $headers[] = "Content-Type: multipart/alternative; boundary=\"{$boundary}\"";

        $message = "This is a multi-part message in MIME format.\r\n";

        $message .= "--{$boundary}\r\n";

        $message .= "Content-Type: text/plain; charset=UTF-8\r\n";

        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

        $message .= $body . "\r\n";

        $message .= "--{$boundary}\r\n";

        $message .= "Content-Type: text/html; charset=UTF-8\r\n";

        $message .= "Content-Transfer-Encoding: 8bit\r\n\r\n";

        $message .= $bodyHtml . "\r\n";

        $message .= "--{$boundary}--\r\n";

        $sent = mail($recipient, $encodedSubject, $message, implode("\r\n", $headers), $params);

        if (!$sent) {

            $sent = $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

        }

        return $sent;

    }

    return $sendPlainFallback($recipient, $encodedSubject, $body, $headers, $params);

}
