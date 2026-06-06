from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"

    def ready(self):
        from django.conf import settings

        if settings.MONITOR_TIMEOUT <= 0:
            raise ValueError("MONITOR_TIMEOUT must be greater than 0.")
        if settings.MONITOR_INTERVAL_SECONDS <= 0:
            raise ValueError("MONITOR_INTERVAL_SECONDS must be greater than 0.")
        if settings.ALERT_CONSECUTIVE_FAILURES <= 0:
            raise ValueError("ALERT_CONSECUTIVE_FAILURES must be greater than 0.")
