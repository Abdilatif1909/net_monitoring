import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .analytics import get_cached_dashboard_payload, get_target_analytics
from .alerts import send_test_telegram_alert
from .forms import MonitorTargetForm
from .models import CHANNEL_EMAIL, CHANNEL_TELEGRAM, MonitorTarget, MonitoringResult, NotificationHistory, STATUS_OFFLINE, STATUS_ONLINE
from .services import bootstrap_default_targets, run_due_targets_monitoring, run_monitoring_for_target
from .utils import build_target_summaries


def _get_overall_status(stats: dict) -> str:
    total_targets = stats["total_targets"]
    online_targets = stats["online_targets"]
    offline_targets = stats["offline_targets"]

    if total_targets == 0:
        return "No data"
    if offline_targets == 0:
        return "Online"
    if online_targets == 0:
        return "Offline"
    return "Degraded"


def _apply_dashboard_filters(request, queryset):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    offline_only = request.GET.get("offline_only", "") == "1"

    if q:
        queryset = queryset.filter(Q(target__name__icontains=q) | Q(host__icontains=q))
    if status:
        queryset = queryset.filter(status=status)
    if offline_only:
        queryset = queryset.filter(status=STATUS_OFFLINE)
    if date_from:
        queryset = queryset.filter(checked_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(checked_at__date__lte=date_to)

    return queryset, {
        "q": q,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "offline_only": offline_only,
    }


def _paginate(queryset, page_number, per_page):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)


def _build_chart_payload(results, target_summaries, analytics):
    ping_trend_results = list(results[:20])[::-1]
    return {
        "chart_labels_json": json.dumps(
            [f"{item.target.name if item.target_id else item.host} {item.checked_at.strftime('%H:%M:%S')}" for item in ping_trend_results]
        ),
        "chart_ping_values_json": json.dumps([item.ping_ms or 0 for item in ping_trend_results]),
        "uptime_labels_json": json.dumps([item["target"].name for item in target_summaries]),
        "uptime_values_json": json.dumps([item["uptime_percentage"] for item in target_summaries]),
        "outage_labels_json": json.dumps([item["name"] for item in analytics["outage_frequency"]]),
        "outage_values_json": json.dumps([item["outage_count"] for item in analytics["outage_frequency"]]),
        "distribution_labels_json": json.dumps(["Fast", "Medium", "Slow", "Offline"]),
        "distribution_values_json": json.dumps(list(analytics["response_distribution"].values())),
    }


def _calculate_response_score(result) -> int:
    if not result or result.status != STATUS_ONLINE or result.response_time_ms is None:
        return 0

    response_time = result.response_time_ms
    if response_time <= 100:
        return 100
    if response_time <= 250:
        return 85
    if response_time <= 500:
        return 65
    if response_time <= 1000:
        return 45
    return 20


def _target_chart_payload(results):
    ordered_results = list(results[:16])[::-1]
    return {
        "recent_labels_json": json.dumps([item.checked_at.strftime("%H:%M:%S") for item in ordered_results]),
        "recent_ping_values_json": json.dumps([item.ping_ms or 0 for item in ordered_results]),
        "recent_response_values_json": json.dumps([item.response_time_ms or 0 for item in ordered_results]),
        "recent_status_values_json": json.dumps([1 if item.status == STATUS_ONLINE else 0 for item in ordered_results]),
    }


def _build_target_check_context(target, latest_result, history_page, page_title, page_subtitle):
    analytics = get_target_analytics(target)
    recent_results = target.results.all()
    response_score = _calculate_response_score(latest_result)
    telegram_notification = target.notifications.filter(channel=CHANNEL_TELEGRAM).first()
    email_notification = target.notifications.filter(channel=CHANNEL_EMAIL).first()
    last_checked_display = latest_result.checked_at.strftime("%Y-%m-%d %H:%M:%S") if latest_result and latest_result.checked_at else "-"
    ping_display = f"{(latest_result.ping_ms or 0):.2f} ms" if latest_result and latest_result.ping_ms is not None else "-"
    response_display = (
        f"Response: {(latest_result.response_time_ms or 0):.2f} ms"
        if latest_result and latest_result.response_time_ms is not None
        else "Response: -"
    )
    ip_display = latest_result.ip_address if latest_result and latest_result.ip_address else "-"
    http_display = str(latest_result.response_status_code) if latest_result and latest_result.response_status_code else "-"
    telegram_status_display = "Telegram OK" if telegram_notification and telegram_notification.success else "No recent alert"
    email_status_display = "Email OK" if email_notification and email_notification.success else "No recent email"
    response_progress_class = "bg-success" if response_score >= 80 else "bg-warning" if response_score >= 50 else "bg-danger"

    context = {
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "target": target,
        "latest_result": latest_result,
        "history_page": history_page,
        "recent_checks": history_page.object_list,
        "analytics": analytics,
        "response_score": response_score,
        "auto_refresh_seconds": max(target.check_interval, settings.MONITOR_INTERVAL_SECONDS),
        "telegram_notification": telegram_notification,
        "email_notification": email_notification,
        "status_card_checked_at": f"Last checked: {last_checked_display}",
        "status_card_ping": ping_display,
        "status_card_response": response_display,
        "status_card_http": http_display,
        "status_card_ip": f"IP: {ip_display}",
        "status_card_alerts": f"{response_score}%",
        "status_card_alerts_subtitle": telegram_status_display,
        "response_progress_class": response_progress_class,
        "telegram_status_display": telegram_status_display,
        "email_status_display": email_status_display,
        **_target_chart_payload(recent_results),
    }
    return context


def _render_monitor_not_found(request, title, message):
    return render(
        request,
        "monitoring/not_found.html",
        {
            "page_title": title,
            "message": message,
        },
        status=404,
    )


def _get_monitor_target_or_404_response(request, target_id):
    target = MonitorTarget.objects.filter(pk=target_id).first()
    if target is None:
        return None, _render_monitor_not_found(
            request,
            title="Target topilmadi",
            message="So‘ralgan monitoring target mavjud emas yoki o‘chirilgan.",
        )
    return target, None


def _build_telegram_test_context(success, message, *, run_test, last_sent_override=None):
    latest_notification = NotificationHistory.objects.filter(channel=CHANNEL_TELEGRAM).select_related("target").first()
    last_sent_time = last_sent_override or (latest_notification.sent_at if latest_notification else None)
    return {
        "page_title": "Telegram monitoring test",
        "page_subtitle": "Bot aloqa holati va xabar yuborish natijasi.",
        "telegram_success": success,
        "telegram_message": message,
        "run_test": run_test,
        "chat_id": settings.TELEGRAM_CHAT_ID or "Not configured",
        "bot_token_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "last_sent_time": last_sent_time,
        "last_target_name": latest_notification.target.name if latest_notification else None,
        "connection_status": "Connected" if success else "Error",
        "connection_badge": "success" if success else "danger",
    }


def _serialize_target_check_charts(context):
    return {
        "labels": json.loads(context["recent_labels_json"]),
        "ping_values": json.loads(context["recent_ping_values_json"]),
        "response_values": json.loads(context["recent_response_values_json"]),
        "status_values": json.loads(context["recent_status_values_json"]),
    }


def _build_target_check_page_context(
    target,
    page_number,
    *,
    force_check,
    page_title,
    page_subtitle,
    live_mode,
):
    monitoring_data = {
        "result": target.results.first(),
        "status_changed": False,
        "notification_sent": False,
        "email_sent": False,
    }
    if force_check:
        monitoring_data = run_monitoring_for_target(target, force=True)

    latest_result = monitoring_data["result"] or target.results.first()
    history_page = _paginate(target.results.all(), page_number, 12)
    context = _build_target_check_context(
        target=target,
        latest_result=latest_result,
        history_page=history_page,
        page_title=page_title,
        page_subtitle=page_subtitle,
    )
    context.update(
        {
            "status_changed": monitoring_data.get("status_changed", False),
            "notification_sent": monitoring_data.get("notification_sent", False),
            "email_sent": monitoring_data.get("email_sent", False),
            "live_mode": live_mode,
        }
    )
    return context


def _build_dashboard_context(request):
    bootstrap_default_targets()
    cached_payload = get_cached_dashboard_payload()
    stats = cached_payload["stats"]
    analytics = cached_payload["analytics"]
    all_results = MonitoringResult.objects.select_related("target")
    filtered_results, filters = _apply_dashboard_filters(request, all_results)
    filtered_outages, _ = _apply_dashboard_filters(request, all_results.filter(status=STATUS_OFFLINE))

    recent_results_page = _paginate(filtered_results, request.GET.get("page"), 8)
    outages_page = _paginate(filtered_outages, request.GET.get("outage_page"), 6)
    target_summaries = build_target_summaries(MonitorTarget.objects.all())
    latest_result = recent_results_page.object_list[0] if recent_results_page.object_list else None
    overall_status = _get_overall_status(stats)
    last_checked = latest_result.checked_at if latest_result else None
    recent_outages = list(outages_page.object_list)
    last_changed = recent_outages[0].checked_at if recent_outages else last_checked
    chart_payload = _build_chart_payload(filtered_results, target_summaries, analytics)

    context = {
        "page_title": "Masofaviy internet monitoring tizimi",
        "latest_result": latest_result,
        "latest_results_page": recent_results_page,
        "recent_outages_page": outages_page,
        "recent_outages": recent_outages,
        "current_status": overall_status,
        "last_changed": last_changed,
        "total_checks": stats["total_checks"],
        "offline_count": stats["offline_count"],
        "average_ping": stats["average_ping"],
        "average_response": stats["average_response"],
        "overall_uptime": stats["overall_uptime"],
        "total_targets": stats["total_targets"],
        "online_targets": stats["online_targets"],
        "offline_targets": stats["offline_targets"],
        "last_checked": last_checked,
        "monitor_interval_seconds": settings.MONITOR_INTERVAL_SECONDS,
        "target_summaries": target_summaries,
        "target_form": MonitorTargetForm(initial={"check_interval": settings.MONITOR_INTERVAL_SECONDS}),
        "filters": filters,
        "top_slow_websites": analytics["top_slow_websites"],
        "most_unstable_targets": analytics["most_unstable_targets"],
        "outage_frequency": analytics["outage_frequency"],
        "response_distribution": analytics["response_distribution"],
        "recent_notifications": analytics["recent_notifications"],
        **chart_payload,
    }
    return context


@login_required
def dashboard(request):
    return render(request, "monitoring/dashboard.html", _build_dashboard_context(request))


class TargetListView(LoginRequiredMixin, ListView):
    model = MonitorTarget
    template_name = "monitoring/targets/list.html"
    context_object_name = "targets"

    def get_queryset(self):
        bootstrap_default_targets()
        return MonitorTarget.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Monitor targetlar"
        context["target_summaries"] = build_target_summaries(context["targets"])
        return context


class TargetCreateView(LoginRequiredMixin, CreateView):
    model = MonitorTarget
    form_class = MonitorTargetForm
    template_name = "monitoring/targets/form.html"
    success_url = reverse_lazy("monitoring:target-list")

    def form_valid(self, form):
        messages.success(self.request, "Yangi target muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Yangi target qo'shish"
        context["submit_label"] = "Saqlash"
        return context


class TargetUpdateView(LoginRequiredMixin, UpdateView):
    model = MonitorTarget
    form_class = MonitorTargetForm
    template_name = "monitoring/targets/form.html"
    success_url = reverse_lazy("monitoring:target-list")

    def form_valid(self, form):
        messages.success(self.request, "Target ma'lumotlari yangilandi.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Targetni tahrirlash"
        context["submit_label"] = "Yangilash"
        return context


class TargetDeleteView(LoginRequiredMixin, DeleteView):
    model = MonitorTarget
    template_name = "monitoring/targets/confirm_delete.html"
    success_url = reverse_lazy("monitoring:target-list")

    def form_valid(self, form):
        messages.success(self.request, "Target o'chirildi.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Targetni o'chirish"
        return context


@login_required
def target_create_from_dashboard(request):
    if request.method != "POST":
        return redirect("monitoring:dashboard")

    form = MonitorTargetForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Target dashboard orqali qo'shildi.")
    else:
        messages.error(request, "Target qo'shishda xatolik yuz berdi.")
    return redirect("monitoring:dashboard")


@login_required
def target_detail(request, pk: int):
    target = get_object_or_404(MonitorTarget, pk=pk)
    analytics = get_target_analytics(target)
    history_page = _paginate(target.results.all(), request.GET.get("page"), 10)
    outages_page = _paginate(target.results.filter(status=STATUS_OFFLINE), request.GET.get("outage_page"), 6)

    context = {
        "page_title": f"{target.name} detail",
        "target": target,
        "analytics": analytics,
        "history_page": history_page,
        "outages_page": outages_page,
        "ping_labels_json": json.dumps([item.checked_at.strftime("%H:%M:%S") for item in analytics["recent_results"][::-1]]),
        "ping_values_json": json.dumps([item.ping_ms or 0 for item in analytics["recent_results"][::-1]]),
        "response_values_json": json.dumps([item.response_time_ms or 0 for item in analytics["recent_results"][::-1]]),
    }
    return render(request, "monitoring/targets/detail.html", context)


@login_required
def target_check_view(request, target_id: int):
    target, not_found_response = _get_monitor_target_or_404_response(request, target_id)
    if not_found_response is not None:
        return not_found_response
    context = _build_target_check_page_context(
        target=target,
        page_number=request.GET.get("page"),
        force_check=True,
        page_title=f"{target.name} live check",
        page_subtitle="UptimeRobot/Pingdom style live monitoring summary.",
        live_mode=True,
    )
    context["target_live_data_url"] = reverse_lazy("monitoring:target-check-live-data", kwargs={"target_id": target.id})
    return render(request, "monitoring/target_check.html", context)


@login_required
def target_history_view(request, target_id: int):
    target, not_found_response = _get_monitor_target_or_404_response(request, target_id)
    if not_found_response is not None:
        return not_found_response
    context = _build_target_check_page_context(
        target=target,
        page_number=request.GET.get("page"),
        force_check=False,
        page_title=f"{target.name} monitoring history",
        page_subtitle="Recent checks, response trend, and availability history.",
        live_mode=False,
    )
    context["target_live_data_url"] = reverse_lazy("monitoring:target-check-live-data", kwargs={"target_id": target.id})
    return render(request, "monitoring/target_check.html", context)


@login_required
@require_GET
def target_check_live_data(request, target_id: int):
    target = get_object_or_404(MonitorTarget, pk=target_id)
    should_force_check = request.GET.get("run_check", "1") == "1"
    context = _build_target_check_page_context(
        target=target,
        page_number=request.GET.get("page"),
        force_check=should_force_check,
        page_title=f"{target.name} live check",
        page_subtitle="UptimeRobot/Pingdom style live monitoring summary.",
        live_mode=True,
    )
    html = render_to_string("monitoring/partials/target_check_live_root.html", context, request=request)
    return JsonResponse(
        {
            "html": html,
            "charts": _serialize_target_check_charts(context),
            "status": context["latest_result"].status if context.get("latest_result") else None,
            "last_checked": context["latest_result"].checked_at.isoformat() if context.get("latest_result") else None,
        }
    )


@login_required
def monitor_target_check_view(request, target_id: int):
    target, not_found_response = _get_monitor_target_or_404_response(request, target_id)
    if not_found_response is not None:
        return not_found_response

    context = _build_target_check_page_context(
        target=target,
        page_number=request.GET.get("page"),
        force_check=True,
        page_title=f"{target.name} live check",
        page_subtitle="UptimeRobot/Pingdom style live monitoring summary.",
        live_mode=True,
    )
    context["target_live_data_url"] = reverse_lazy("monitoring:monitor-target-check-live-data", kwargs={"target_id": target.id})
    return render(request, "monitoring/target_check.html", context)


@login_required
def telegram_test_view(request):
    run_test = request.GET.get("run_test", "1") == "1"
    if run_test:
        success = send_test_telegram_alert()
        message = "Telegram test xabari yuborildi." if success else "Telegram xabar yuborishda xatolik yuz berdi."
        last_sent_override = timezone.now() if success else None
    else:
        latest_notification = NotificationHistory.objects.filter(channel=CHANNEL_TELEGRAM).first()
        success = latest_notification.success if latest_notification else False
        message = "Oxirgi Telegram holati ko‘rsatildi."
        last_sent_override = None

    context = _build_telegram_test_context(success, message, run_test=run_test, last_sent_override=last_sent_override)
    context["telegram_live_data_url"] = reverse_lazy("monitoring:monitor-telegram-test-live-data")
    return render(request, "monitoring/telegram_test.html", context)


@login_required
@require_GET
def telegram_test_live_data(request):
    run_test = request.GET.get("run_test", "1") == "1"
    if run_test:
        success = send_test_telegram_alert()
        message = "Telegram test xabari yuborildi." if success else "Telegram xabar yuborishda xatolik yuz berdi."
        last_sent_override = timezone.now() if success else None
    else:
        latest_notification = NotificationHistory.objects.filter(channel=CHANNEL_TELEGRAM).first()
        success = latest_notification.success if latest_notification else False
        message = "Oxirgi Telegram holati ko‘rsatildi."
        last_sent_override = None

    context = _build_telegram_test_context(success, message, run_test=run_test, last_sent_override=last_sent_override)
    html = render_to_string("monitoring/partials/telegram_test_root.html", context, request=request)
    return JsonResponse(
        {
            "html": html,
            "success": success,
            "message": message,
            "last_sent_time": context["last_sent_time"].isoformat() if context["last_sent_time"] else None,
        }
    )


@login_required
@require_GET
def dashboard_partial(request):
    run_due_targets_monitoring(force=False)
    context = _build_dashboard_context(request)
    widgets_html = render_to_string("monitoring/partials/widgets.html", context, request=request)
    targets_html = render_to_string("monitoring/partials/targets_table.html", context, request=request)
    results_html = render_to_string("monitoring/partials/results_table.html", context, request=request)
    outages_html = render_to_string("monitoring/partials/outages_list.html", context, request=request)
    analytics_html = render_to_string("monitoring/partials/analytics_panels.html", context, request=request)

    return JsonResponse(
        {
            "widgets_html": widgets_html,
            "targets_html": targets_html,
            "results_html": results_html,
            "outages_html": outages_html,
            "analytics_html": analytics_html,
            "charts": {
                "ping_labels": json.loads(context["chart_labels_json"]),
                "ping_values": json.loads(context["chart_ping_values_json"]),
                "uptime_labels": json.loads(context["uptime_labels_json"]),
                "uptime_values": json.loads(context["uptime_values_json"]),
                "outage_labels": json.loads(context["outage_labels_json"]),
                "outage_values": json.loads(context["outage_values_json"]),
                "distribution_labels": json.loads(context["distribution_labels_json"]),
                "distribution_values": json.loads(context["distribution_values_json"]),
            },
        }
    )


@require_GET
def health_check(request):
    db_status = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_status = "error"

    last_check = MonitoringResult.objects.order_by("-checked_at").values_list("checked_at", flat=True).first()
    monitoring_status = "idle" if last_check is None else "ok"

    return JsonResponse(
        {
            "app_status": "ok",
            "db_status": db_status,
            "monitoring_status": monitoring_status,
            "last_check": last_check.isoformat() if last_check else None,
        }
    )


@login_required
def export_results_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="monitoring_results.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Target",
            "Host",
            "IP Address",
            "Status",
            "Ping (ms)",
            "HTTP Status",
            "Response Time (ms)",
            "Checked At",
            "Error Message",
        ]
    )

    for item in MonitoringResult.objects.select_related("target").all():
        writer.writerow(
            [
                item.target.name if item.target_id else "",
                item.host,
                item.ip_address or "",
                item.status,
                item.ping_ms if item.ping_ms is not None else "",
                item.response_status_code if item.response_status_code is not None else "",
                item.response_time_ms if item.response_time_ms is not None else "",
                item.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
                item.error_message,
            ]
        )

    return response


@login_required
def export_target_data(request, pk: int):
    target = get_object_or_404(MonitorTarget, pk=pk)
    export_format = request.GET.get("format", "csv")
    export_type = request.GET.get("type", "history")

    if export_type == "outages":
        queryset = target.results.filter(status=STATUS_OFFLINE)
    else:
        queryset = target.results.all()

    if export_type == "statistics":
        payload = get_target_analytics(target)
        statistics_data = {
            "target": target.name,
            "daily_uptime": payload["daily_uptime"],
            "weekly_uptime": payload["weekly_uptime"],
            "monthly_uptime": payload["monthly_uptime"],
            "avg_response_time": payload["average_response_time"],
            "max_response_time": payload["max_response_time"],
            "outage_count": payload["outage_count"],
        }
        if export_format == "json":
            return JsonResponse(statistics_data)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{target.name}_statistics.csv"'
        writer = csv.writer(response)
        writer.writerow(["Metric", "Value"])
        for key, value in statistics_data.items():
            writer.writerow([key, value])
        return response

    if export_format == "json":
        return JsonResponse(
            {
                "target": target.name,
                "type": export_type,
                "results": [
                    {
                        "status": item.status,
                        "host": item.host,
                        "ping_ms": item.ping_ms,
                        "response_status_code": item.response_status_code,
                        "response_time_ms": item.response_time_ms,
                        "checked_at": item.checked_at.isoformat(),
                        "error_message": item.error_message,
                    }
                    for item in queryset
                ],
            }
        )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{target.name}_{export_type}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Status", "Host", "Ping", "HTTP", "Response", "Checked At", "Error"])
    for item in queryset:
        writer.writerow(
            [
                item.status,
                item.host,
                item.ping_ms or "",
                item.response_status_code or "",
                item.response_time_ms or "",
                item.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
                item.error_message,
            ]
        )
    return response
