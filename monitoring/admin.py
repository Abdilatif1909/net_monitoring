from django.contrib import admin
from django.utils.html import format_html

from .models import MonitorTarget, MonitoringResult, MonitoringState


@admin.register(MonitorTarget)
class MonitorTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "is_active", "check_interval", "last_status_badge", "updated_at")
    list_filter = ("is_active", "last_status")
    search_fields = ("name", "url")
    ordering = ("name",)

    def last_status_badge(self, obj):
        colors = {
            "online": "#198754",
            "offline": "#dc3545",
            "unknown": "#6c757d",
        }
        return format_html(
            '<strong style="color: {}">{}</strong>',
            colors.get(obj.last_status, "#6c757d"),
            obj.get_last_status_display(),
        )

    last_status_badge.short_description = "Last status"


@admin.register(MonitoringResult)
class MonitoringResultAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "host",
        "ip_address",
        "status_badge",
        "ping_display",
        "response_status_code",
        "response_time_display",
        "checked_at",
    )
    list_filter = ("status", "target", "checked_at")
    search_fields = ("host", "ip_address", "target__name", "target__url")
    ordering = ("-checked_at",)
    readonly_fields = ("checked_at",)

    def status_badge(self, obj):
        color = "#198754" if obj.status == "online" else "#dc3545"
        return format_html('<strong style="color: {}">{}</strong>', color, obj.get_status_display())

    status_badge.short_description = "Status"

    def ping_display(self, obj):
        if obj.ping_ms is None:
            return "-"
        return f"{obj.ping_ms} ms"

    ping_display.short_description = "Ping"

    def response_time_display(self, obj):
        if obj.response_time_ms is None:
            return "-"
        return f"{obj.response_time_ms} ms"

    response_time_display.short_description = "Response"


@admin.register(MonitoringState)
class MonitoringStateAdmin(admin.ModelAdmin):
    list_display = ("target", "is_online", "last_changed")
    readonly_fields = ("last_changed",)
