import logging

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("monitoring.alerts")


def send_telegram_message(message: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.info("Telegram settings are not configured; skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Failed to send Telegram message.")
        return False


def build_offline_telegram_message(result, severity: str) -> str:
    checked_at = timezone.localtime(result.checked_at).strftime("%Y-%m-%d %H:%M:%S")
    target_name = result.target.name if result.target_id else result.host
    emoji = "🟠" if severity == "warning" else "🚨"
    title = "Target warning holatda" if severity == "warning" else "Target critical offline"
    return (
        f"{emoji} <b>{title}</b>\n"
        f"Target: {target_name}\n"
        f"URL/Host: {result.host}\n"
        f"IP: {result.ip_address or '-'}\n"
        f"HTTP: {result.response_status_code or '-'}\n"
        f"Xatolik: {result.error_message or 'Javob kelmadi'}\n"
        f"Vaqt: {checked_at}"
    )


def internet_offline_alert(result, severity: str = "warning") -> bool:
    message = build_offline_telegram_message(result, severity)
    return send_telegram_message(message)


def build_restored_telegram_message(result) -> str:
    checked_at = timezone.localtime(result.checked_at).strftime("%Y-%m-%d %H:%M:%S")
    target_name = result.target.name if result.target_id else result.host
    ping_value = f"{result.ping_ms} ms" if result.ping_ms is not None else "-"
    response_time = f"{result.response_time_ms} ms" if result.response_time_ms is not None else "-"
    return (
        "✅ <b>Target qayta tiklandi</b>\n"
        f"Target: {target_name}\n"
        f"URL/Host: {result.host}\n"
        f"HTTP: {result.response_status_code or '-'}\n"
        f"Ping: {ping_value}\n"
        f"Response: {response_time}\n"
        f"Vaqt: {checked_at}"
    )


def internet_restored_alert(result) -> bool:
    message = build_restored_telegram_message(result)
    return send_telegram_message(message)


def send_test_telegram_alert() -> bool:
    checked_at = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        "🧪 <b>Telegram test xabari</b>\n"
        "Internet monitoring tizimi ishlayapti.\n"
        f"Vaqt: {checked_at}"
    )
    return send_telegram_message(message)
