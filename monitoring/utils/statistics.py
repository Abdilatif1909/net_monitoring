from django.db.models import Avg

from monitoring.models import MonitorTarget, MonitoringResult, STATUS_OFFLINE, STATUS_ONLINE



def get_monitoring_statistics(target=None) -> dict:
    queryset = MonitoringResult.objects.select_related("target")
    if target is not None:
        queryset = queryset.filter(target=target)

    total_checks = queryset.count()
    offline_count = queryset.filter(status=STATUS_OFFLINE).count()
    online_count = queryset.filter(status=STATUS_ONLINE).count()
    average_ping = queryset.filter(status=STATUS_ONLINE).aggregate(avg_ping=Avg("ping_ms"))["avg_ping"]
    average_response = queryset.filter(status=STATUS_ONLINE).aggregate(avg_response=Avg("response_time_ms"))["avg_response"]
    last_outage = queryset.filter(status=STATUS_OFFLINE).first()
    uptime_percentage = round((online_count / total_checks) * 100, 2) if total_checks else 0

    return {
        "total_checks": total_checks,
        "offline_count": offline_count,
        "online_count": online_count,
        "average_ping": average_ping,
        "average_response": average_response,
        "uptime_percentage": uptime_percentage,
        "last_outage": last_outage,
    }



def get_target_statistics(target) -> dict:
    stats = get_monitoring_statistics(target=target)
    stats["target"] = target
    return stats



def build_target_summaries(queryset=None) -> list[dict]:
    targets = queryset if queryset is not None else MonitorTarget.objects.all()
    summaries = []
    for target in targets:
        latest_result = target.results.first()
        stats = get_target_statistics(target)
        summaries.append(
            {
                "target": target,
                "latest_result": latest_result,
                "uptime_percentage": stats["uptime_percentage"],
                "downtime_count": stats["offline_count"],
                "average_response": stats["average_response"],
                "last_outage": stats["last_outage"],
            }
        )
    return summaries



def get_dashboard_statistics() -> dict:
    active_targets = MonitorTarget.objects.filter(is_active=True)
    target_summaries = build_target_summaries(active_targets)
    total_targets = active_targets.count()
    online_targets = sum(1 for item in target_summaries if item["target"].last_status == STATUS_ONLINE)
    offline_targets = sum(1 for item in target_summaries if item["target"].last_status == STATUS_OFFLINE)
    overall_uptime = round(
        sum(item["uptime_percentage"] for item in target_summaries) / total_targets,
        2,
    ) if total_targets else 0

    global_stats = get_monitoring_statistics()
    global_stats.update(
        {
            "total_targets": total_targets,
            "online_targets": online_targets,
            "offline_targets": offline_targets,
            "overall_uptime": overall_uptime,
            "target_summaries": target_summaries,
        }
    )
    return global_stats
