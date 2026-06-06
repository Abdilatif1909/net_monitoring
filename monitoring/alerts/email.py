import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger("monitoring.alerts")


def send_email_alert(subject: str, message: str) -> bool:
    if not settings.ALERT_EMAIL_RECIPIENTS:
        logger.info("Email recipients are not configured; skipping email alert.")
        return False

    from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
    if not from_email:
        logger.warning("DEFAULT_FROM_EMAIL or EMAIL_HOST_USER must be configured for email alerts.")
        return False

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=list(settings.ALERT_EMAIL_RECIPIENTS),
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send email alert.")
        return False


def build_offline_email_payload(result, severity: str) -> tuple[str, str]:
    checked_at = timezone.localtime(result.checked_at).strftime("%Y-%m-%d %H:%M:%S")
    target_name = result.target.name if result.target_id else result.host
    severity_label = severity.upper()
    subject = f"[{severity_label}] {target_name}"
    message = (
        "Website monitoring tizimi ogohlantirishi\n\n"
        f"Severity: {severity_label}\n"
        f"Target: {target_name}\n"
        f"URL/Host: {result.host}\n"
        f"IP: {result.ip_address or '-'}\n"
        f"HTTP status: {result.response_status_code or '-'}\n"
        f"Ping: {result.ping_ms if result.ping_ms is not None else '-'} ms\n"
        f"Response time: {result.response_time_ms if result.response_time_ms is not None else '-'} ms\n"
        f"Tekshiruv vaqti: {checked_at}\n"
        f"Xatolik: {result.error_message or 'Javob kelmadi'}"
    )
    return subject, message


def internet_offline_email_alert(result, severity: str = "warning") -> bool:
    subject, message = build_offline_email_payload(result, severity)
    return send_email_alert(subject, message)


def build_restored_email_payload(result) -> tuple[str, str]:
    checked_at = timezone.localtime(result.checked_at).strftime("%Y-%m-%d %H:%M:%S")
    target_name = result.target.name if result.target_id else result.host
    subject = f"[RESTORED] {target_name}"
    message = (
        "Website monitoring tizimi ogohlantirishi\n\n"
        f"Target: {target_name}\n"
        f"URL/Host: {result.host}\n"
        f"IP: {result.ip_address or '-'}\n"
        f"HTTP status: {result.response_status_code or '-'}\n"
        f"Ping: {result.ping_ms if result.ping_ms is not None else '-'} ms\n"
        f"Response time: {result.response_time_ms if result.response_time_ms is not None else '-'} ms\n"
        f"Tekshiruv vaqti: {checked_at}"
    )
    return subject, message


def internet_restored_email_alert(result) -> bool:
    subject, message = build_restored_email_payload(result)
    return send_email_alert(subject, message)
