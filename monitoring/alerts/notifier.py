from monitoring.models import (
    CHANNEL_EMAIL,
    CHANNEL_TELEGRAM,
    NotificationHistory,
    SEVERITY_WARNING,
)

from .email import (
    build_offline_email_payload,
    build_restored_email_payload,
    internet_offline_email_alert,
    internet_restored_email_alert,
)
from .telegram import (
    build_offline_telegram_message,
    build_restored_telegram_message,
    internet_offline_alert,
    internet_restored_alert,
)


def _create_history(target, channel: str, message: str, severity: str, success: bool) -> None:
    NotificationHistory.objects.create(
        target=target,
        channel=channel,
        message=message,
        severity=severity,
        success=success,
    )


def send_offline_notifications(result, severity: str = SEVERITY_WARNING) -> dict:
    telegram_message = build_offline_telegram_message(result, severity)
    email_subject, email_message = build_offline_email_payload(result, severity)
    telegram_sent = internet_offline_alert(result, severity=severity)
    email_sent = internet_offline_email_alert(result, severity=severity)

    _create_history(result.target, CHANNEL_TELEGRAM, telegram_message, severity, telegram_sent)
    _create_history(result.target, CHANNEL_EMAIL, f"{email_subject}\n\n{email_message}", severity, email_sent)

    return {
        "telegram_sent": telegram_sent,
        "email_sent": email_sent,
    }


def send_restored_notifications(result) -> dict:
    telegram_message = build_restored_telegram_message(result)
    email_subject, email_message = build_restored_email_payload(result)
    telegram_sent = internet_restored_alert(result)
    email_sent = internet_restored_email_alert(result)

    _create_history(result.target, CHANNEL_TELEGRAM, telegram_message, SEVERITY_WARNING, telegram_sent)
    _create_history(result.target, CHANNEL_EMAIL, f"{email_subject}\n\n{email_message}", SEVERITY_WARNING, email_sent)

    return {
        "telegram_sent": telegram_sent,
        "email_sent": email_sent,
    }
