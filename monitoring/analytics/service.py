from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from monitoring.models import MonitorTarget, MonitoringResult, NotificationHistory, STATUS_OFFLINE, STATUS_ONLINE
from monitoring.utils import build_target_summaries, get_dashboard_statistics, get_target_statistics

CACHE_KEY = "monitoring.dashboard.analytics"
CACHE_TIMEOUT = 60



def _period_uptime(target, since):
    queryset = target.results.filter(checked_at__gte=since)
    total = queryset.count()
    online = queryset.filter(status=STATUS_ONLINE).count()
    return round((online / total) * 100, 2) if total else 0



def get_target_analytics(target):
    now = timezone.now()
    queryset = target.results.all()
    average_response_time = queryset.filter(status=STATUS_ONLINE).aggregate(value=Avg("response_time_ms"))["value"]
    success_count = queryset.filter(status=STATUS_ONLINE).count()
    return {
        "daily_uptime": _period_uptime(target, now - timedelta(days=1)),
        "weekly_uptime": _period_uptime(target, now - timedelta(days=7)),
        "monthly_uptime": _period_uptime(target, now - timedelta(days=30)),
        "average_response_time": round(average_response_time or 0, 2),
        "max_response_time": queryset.aggregate(value=Max("response_time_ms"))["value"],
        "outage_count": queryset.filter(status=STATUS_OFFLINE).count(),
        "success_count": success_count,
        "last_alerts": target.notifications.all()[:10],
        "recent_results": queryset[:20],
        "recent_outages": queryset.filter(status=STATUS_OFFLINE)[:10],
        "stats": get_target_statistics(target),
    }



def get_platform_analytics():
    target_stats = build_target_summaries(MonitorTarget.objects.filter(is_active=True))
    top_slow_websites = [
        {
            "name": item["target"].name,
            "avg_response_time": round(item["average_response"] or 0, 2),
        }
        for item in sorted(target_stats, key=lambda item: item["average_response"] or 0, reverse=True)[:5]
    ]
    most_unstable_targets = [
        {
            "name": item["target"].name,
            "outage_count": item["downtime_count"],
        }
        for item in sorted(target_stats, key=lambda item: item["downtime_count"], reverse=True)[:5]
    ]

    outage_frequency = list(
        MonitorTarget.objects.filter(is_active=True)
        .annotate(outage_count=Count("results", filter=Q(results__status=STATUS_OFFLINE)))
        .values("name", "outage_count")
        .order_by("-outage_count")[:10]
    )

    response_distribution = {
        "fast": MonitoringResult.objects.filter(response_time_ms__lt=200, status=STATUS_ONLINE).count(),
        "medium": MonitoringResult.objects.filter(response_time_ms__gte=200, response_time_ms__lt=500, status=STATUS_ONLINE).count(),
        "slow": MonitoringResult.objects.filter(response_time_ms__gte=500, status=STATUS_ONLINE).count(),
        "offline": MonitoringResult.objects.filter(status=STATUS_OFFLINE).count(),
    }

    return {
        "top_slow_websites": top_slow_websites,
        "most_unstable_targets": most_unstable_targets,
        "outage_frequency": outage_frequency,
        "response_distribution": response_distribution,
        "recent_notifications": NotificationHistory.objects.select_related("target").all()[:10],
    }



def get_cached_dashboard_payload():
    payload = cache.get(CACHE_KEY)
    if payload is not None:
        return payload

    payload = {
        "stats": get_dashboard_statistics(),
        "analytics": get_platform_analytics(),
    }
    cache.set(CACHE_KEY, payload, CACHE_TIMEOUT)
    return payload
