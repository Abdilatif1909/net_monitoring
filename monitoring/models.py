from urllib.parse import urlparse

from django.db import models
from django.utils import timezone

STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_UNKNOWN = "unknown"

RESULT_STATUS_CHOICES = (
    (STATUS_ONLINE, "Online"),
    (STATUS_OFFLINE, "Offline"),
)

SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

SEVERITY_CHOICES = (
    (SEVERITY_WARNING, "Warning"),
    (SEVERITY_CRITICAL, "Critical"),
)

CHANNEL_TELEGRAM = "telegram"
CHANNEL_EMAIL = "email"

CHANNEL_CHOICES = (
    (CHANNEL_TELEGRAM, "Telegram"),
    (CHANNEL_EMAIL, "Email"),
)

TARGET_STATUS_CHOICES = (
    (STATUS_ONLINE, "Online"),
    (STATUS_OFFLINE, "Offline"),
    (STATUS_UNKNOWN, "Unknown"),
)


class MonitorTarget(models.Model):
    name = models.CharField(max_length=150, unique=True)
    url = models.URLField(unique=True)
    is_active = models.BooleanField(default=True)
    check_interval = models.PositiveIntegerField(default=30, help_text="Sekundlarda monitoring intervali.")
    last_status = models.CharField(max_length=10, choices=TARGET_STATUS_CHOICES, default=STATUS_UNKNOWN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "last_status"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def hostname(self) -> str:
        parsed = urlparse(self.url)
        return parsed.hostname or self.url


class MonitoringResult(models.Model):
    target = models.ForeignKey(
        MonitorTarget,
        on_delete=models.CASCADE,
        related_name="results",
        blank=True,
        null=True,
    )
    host = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=RESULT_STATUS_CHOICES)
    ping_ms = models.FloatField(blank=True, null=True)
    response_status_code = models.PositiveIntegerField(blank=True, null=True)
    response_time_ms = models.FloatField(blank=True, null=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["target", "-checked_at"]),
            models.Index(fields=["status", "-checked_at"]),
            models.Index(fields=["response_status_code"]),
        ]

    def __str__(self):
        target_name = self.target.name if self.target_id else self.host
        return f"{target_name} - {self.status} ({self.checked_at:%Y-%m-%d %H:%M:%S})"


class MonitoringState(models.Model):
    target = models.OneToOneField(
        MonitorTarget,
        on_delete=models.CASCADE,
        related_name="monitoring_state",
        blank=True,
        null=True,
    )
    is_online = models.BooleanField(default=True)
    last_changed = models.DateTimeField(default=timezone.now)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_notification_sent_at = models.DateTimeField(blank=True, null=True)
    last_notification_severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        blank=True,
    )

    class Meta:
        verbose_name = "Monitoring state"
        verbose_name_plural = "Monitoring states"

    def __str__(self):
        if self.target_id:
            return f"{self.target.name}: {'Online' if self.is_online else 'Offline'}"
        return "Online" if self.is_online else "Offline"


class NotificationHistory(models.Model):
    target = models.ForeignKey(
        MonitorTarget,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["target", "-sent_at"]),
            models.Index(fields=["channel", "severity"]),
        ]

    def __str__(self):
        return f"{self.target.name} | {self.channel} | {self.severity}"
