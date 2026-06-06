from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from monitoring.alerts import send_test_telegram_alert
from monitoring.api.serializers import MonitorTargetSerializer, MonitoringResultSerializer
from monitoring.models import MonitorTarget, MonitoringResult
from monitoring.services import run_due_targets_monitoring, run_monitoring_for_target


class MonitorTargetListCreateAPIView(generics.ListCreateAPIView):
    queryset = MonitorTarget.objects.all()
    serializer_class = MonitorTargetSerializer
    permission_classes = [IsAuthenticated]


class MonitorTargetDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MonitorTarget.objects.all()
    serializer_class = MonitorTargetSerializer
    permission_classes = [IsAuthenticated]


class MonitoringResultListAPIView(generics.ListAPIView):
    serializer_class = MonitoringResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = MonitoringResult.objects.select_related("target").all()
        target_id = self.request.query_params.get("target")
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        return queryset


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_all_targets_api(request):
    monitoring_data = run_due_targets_monitoring(force=False)
    results = monitoring_data["results"]
    serializer = MonitoringResultSerializer(results, many=True)
    return Response(
        {
            "processed_targets": len(results),
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_target_api(request, target_id: int):
    target = get_object_or_404(MonitorTarget, pk=target_id)
    monitoring_data = run_monitoring_for_target(target, force=True)
    serializer = MonitoringResultSerializer(monitoring_data["result"])
    response_data = dict(serializer.data)
    response_data.update(
        {
            "notification_sent": monitoring_data["notification_sent"],
            "email_sent": monitoring_data["email_sent"],
            "status_changed": monitoring_data["status_changed"],
        }
    )
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def telegram_test_api(request):
    sent = send_test_telegram_alert()
    return Response(
        {
            "success": sent,
            "message": "Telegram test xabari yuborildi." if sent else "Telegram xabari yuborilmadi.",
        },
        status=status.HTTP_200_OK,
    )
