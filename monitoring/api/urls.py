from django.urls import path

from .views import (
    MonitorTargetDetailAPIView,
    MonitorTargetListCreateAPIView,
    MonitoringResultListAPIView,
    check_all_targets_api,
    check_target_api,
    telegram_test_api,
)

urlpatterns = [
    path("check/", check_all_targets_api, name="check-all-targets-api"),
    path("check/<int:target_id>/", check_target_api, name="check-target-api"),
    path("telegram-test/", telegram_test_api, name="telegram-test-api"),
    path("targets/", MonitorTargetListCreateAPIView.as_view(), name="target-list-create-api"),
    path("targets/<int:pk>/", MonitorTargetDetailAPIView.as_view(), name="target-detail-api"),
    path("results/", MonitoringResultListAPIView.as_view(), name="results-list-api"),
]
