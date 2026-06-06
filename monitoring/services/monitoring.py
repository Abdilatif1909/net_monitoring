import logging
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

from monitoring.alerts import send_offline_notifications, send_restored_notifications
from monitoring.models import (
    MonitorTarget,
    MonitoringState,
    STATUS_OFFLINE,
    STATUS_ONLINE,
    STATUS_UNKNOWN,
)
from monitoring.services.checks import normalize_target_url, perform_hybrid_check
from monitoring.utils import save_monitoring_result

logger = logging.getLogger(__name__)


def _resolve_alert_severity(consecutive_failures: int) -> str:
    return "critical" if consecutive_failures >= settings.ALERT_CONSECUTIVE_FAILURES + 2 else "warning"


def _cooldown_expired(state, now) -> bool:
    if state.last_notification_sent_at is None:
        return True
    elapsed = (now - state.last_notification_sent_at).total_seconds()
    return elapsed >= settings.ALERT_COOLDOWN_SECONDS



def bootstrap_default_targets() -> None:
    if MonitorTarget.objects.exists():
        return

    for raw_target in settings.MONITOR_TARGETS:
        normalized_url = normalize_target_url(raw_target)
        parsed = urlparse(normalized_url)
        hostname = parsed.hostname or raw_target
        target_name = hostname.replace("www.", "").split(":")[0]
        MonitorTarget.objects.get_or_create(
            url=normalized_url,
            defaults={
                "name": target_name.title(),
                "check_interval": settings.MONITOR_INTERVAL_SECONDS,
                "is_active": True,
                "last_status": STATUS_UNKNOWN,
            },
        )



def is_target_due(target, now=None) -> bool:
    now = now or timezone.now()
    latest_result = target.results.first()
    if latest_result is None:
        return True
    elapsed_seconds = (now - latest_result.checked_at).total_seconds()
    return elapsed_seconds >= target.check_interval



def run_monitoring_for_target(target, force=False) -> dict:
    if not target.is_active and not force:
        return {
            "target": target,
            "result": None,
            "notification_sent": False,
            "email_sent": False,
            "status_changed": False,
            "skipped": True,
        }

    if not force and not is_target_due(target):
        return {
            "target": target,
            "result": None,
            "notification_sent": False,
            "email_sent": False,
            "status_changed": False,
            "skipped": True,
        }

    try:
        result_data = perform_hybrid_check(target, timeout=settings.MONITOR_TIMEOUT)
    except Exception as exc:
        logger.exception("Unexpected monitoring failure for target %s", target.name)
        result_data = {
            "target": target,
            "host": target.url,
            "ip_address": None,
            "status": STATUS_OFFLINE,
            "ping_ms": None,
            "response_status_code": None,
            "response_time_ms": None,
            "error_message": str(exc),
        }

    saved_result = save_monitoring_result(target, result_data)
    current_is_online = saved_result.status == STATUS_ONLINE
    now = timezone.now()

    state, created = MonitoringState.objects.get_or_create(
        target=target,
        defaults={
            "is_online": current_is_online,
            "last_changed": now,
            "consecutive_failures": 0 if current_is_online else 1,
        },
    )

    notification_sent = False
    email_sent = False
    status_changed = False

    if created:
        if not current_is_online:
            state.consecutive_failures = 1
            state.save(update_fields=["consecutive_failures"])
    elif state.is_online != current_is_online:
        status_changed = True
        state.is_online = current_is_online
        state.last_changed = now
        if current_is_online:
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1
        state.save(update_fields=["is_online", "last_changed", "consecutive_failures"])

        if current_is_online:
            alert_result = send_restored_notifications(saved_result)
            notification_sent = alert_result["telegram_sent"]
            email_sent = alert_result["email_sent"]
            state.last_notification_sent_at = now
            state.last_notification_severity = "warning"
            state.save(update_fields=["last_notification_sent_at", "last_notification_severity"])
    elif not current_is_online:
        state.consecutive_failures += 1
        state.save(update_fields=["consecutive_failures"])
    else:
        if state.consecutive_failures != 0:
            state.consecutive_failures = 0
            state.save(update_fields=["consecutive_failures"])

    if not current_is_online and state.consecutive_failures >= settings.ALERT_CONSECUTIVE_FAILURES and _cooldown_expired(state, now):
        severity = _resolve_alert_severity(state.consecutive_failures)
        alert_result = send_offline_notifications(saved_result, severity=severity)
        notification_sent = alert_result["telegram_sent"]
        email_sent = alert_result["email_sent"]
        state.last_notification_sent_at = now
        state.last_notification_severity = severity
        state.save(update_fields=["last_notification_sent_at", "last_notification_severity"])

    logger.info(
        "Monitoring finished for %s with status=%s response=%s ping=%s",
        target.name,
        saved_result.status,
        saved_result.response_status_code,
        saved_result.ping_ms,
    )

    return {
        "target": target,
        "result": saved_result,
        "state": state,
        "notification_sent": notification_sent,
        "email_sent": email_sent,
        "status_changed": status_changed,
        "skipped": False,
        "severity": state.last_notification_severity,
        "consecutive_failures": state.consecutive_failures,
    }



def run_due_targets_monitoring(force=False) -> dict:
    bootstrap_default_targets()
    processed_results = []
    targets = MonitorTarget.objects.filter(is_active=True)

    for target in targets:
        monitoring_data = run_monitoring_for_target(target, force=force)
        if monitoring_data.get("result") is not None:
            processed_results.append(monitoring_data)

    return {
        "results": [item["result"] for item in processed_results],
        "items": processed_results,
    }



def run_monitoring_cycle() -> dict:
    monitoring_data = run_due_targets_monitoring(force=False)
    latest_result = monitoring_data["results"][0] if monitoring_data["results"] else None
    latest_item = monitoring_data["items"][0] if monitoring_data["items"] else None
    return {
        "result": latest_result,
        "notification_sent": latest_item["notification_sent"] if latest_item else False,
        "email_sent": latest_item["email_sent"] if latest_item else False,
        "status_changed": latest_item["status_changed"] if latest_item else False,
        "results": monitoring_data["results"],
        "items": monitoring_data["items"],
    }
