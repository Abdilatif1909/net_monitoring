from django.urls import include, path

from .views import (
    TargetCreateView,
    TargetDeleteView,
    TargetListView,
    TargetUpdateView,
    dashboard,
    dashboard_partial,
    export_results_csv,
    export_target_data,
    health_check,
    monitor_target_check_view,
    target_check_live_data,
    target_check_view,
    target_detail,
    target_history_view,
    target_create_from_dashboard,
    telegram_test_live_data,
    telegram_test_view,
)

app_name = "monitoring"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("dashboard/partial/", dashboard_partial, name="dashboard-partial"),
    path("health/", health_check, name="health"),
    path("targets/", TargetListView.as_view(), name="target-list"),
    path("targets/create/", TargetCreateView.as_view(), name="target-create"),
    path("targets/create/dashboard/", target_create_from_dashboard, name="target-create-dashboard"),
    path("targets/<int:pk>/", target_detail, name="target-detail"),
    path("targets/<int:target_id>/check/", target_check_view, name="target-check"),
    path("targets/<int:target_id>/check/live-data/", target_check_live_data, name="target-check-live-data"),
    path("targets/<int:target_id>/history/", target_history_view, name="target-history"),
    path("monitor/check/<int:target_id>/", monitor_target_check_view, name="monitor-target-check"),
    path("monitor/check/<int:target_id>/live-data/", target_check_live_data, name="monitor-target-check-live-data"),
    path("monitor/telegram-test/", telegram_test_view, name="monitor-telegram-test"),
    path("monitor/telegram-test/live-data/", telegram_test_live_data, name="monitor-telegram-test-live-data"),
    path("targets/<int:pk>/edit/", TargetUpdateView.as_view(), name="target-update"),
    path("targets/<int:pk>/delete/", TargetDeleteView.as_view(), name="target-delete"),
    path("targets/<int:pk>/export/", export_target_data, name="target-export"),
    path("export/csv/", export_results_csv, name="export-results-csv"),
    path("api/", include("monitoring.api.urls")),
]
