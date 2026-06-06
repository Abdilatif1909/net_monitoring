from rest_framework import serializers

from monitoring.models import MonitorTarget, MonitoringResult


class MonitorTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorTarget
        fields = (
            "id",
            "name",
            "url",
            "is_active",
            "check_interval",
            "last_status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("last_status", "created_at", "updated_at")


class MonitoringResultSerializer(serializers.ModelSerializer):
    target_name = serializers.CharField(source="target.name", read_only=True)

    class Meta:
        model = MonitoringResult
        fields = (
            "id",
            "target",
            "target_name",
            "host",
            "ip_address",
            "status",
            "ping_ms",
            "response_status_code",
            "response_time_ms",
            "checked_at",
            "error_message",
        )
