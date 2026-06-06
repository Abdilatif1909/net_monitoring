import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Min
from django.utils import timezone

from monitoring.models import MonitorTarget
from monitoring.services import bootstrap_default_targets, run_due_targets_monitoring


class Command(BaseCommand):
    help = "Internet monitoringni interval bilan ishga tushiradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=settings.MONITOR_INTERVAL_SECONDS,
            help="Tekshiruv intervali sekundlarda. Default: 30",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        bootstrap_default_targets()
        self.stdout.write(self.style.SUCCESS(f"Monitoring boshlandi. Interval: {interval} sekund."))
        self.stdout.write(self.style.WARNING("To'xtatish uchun CTRL+C bosing."))

        try:
            while True:
                monitoring_data = run_due_targets_monitoring(force=False)
                processed_items = monitoring_data["items"]

                if processed_items:
                    for item in processed_items:
                        result = item["result"]
                        checked_at = timezone.localtime(result.checked_at).strftime("%Y-%m-%d %H:%M:%S")
                        ping_value = f"{result.ping_ms} ms" if result.ping_ms is not None else "-"
                        response_value = f"{result.response_time_ms} ms" if result.response_time_ms is not None else "-"
                        notification_text = " | Telegram yuborildi" if item["notification_sent"] else ""
                        email_text = " | Email yuborildi" if item.get("email_sent") else ""
                        status_change_text = " | Status o'zgardi" if item["status_changed"] else ""

                        self.stdout.write(
                            f"[{checked_at}] {result.target.name if result.target_id else result.host} | {result.status.upper()} | ping={ping_value} | response={response_value} | http={result.response_status_code or '-'}{status_change_text}{notification_text}{email_text}"
                        )
                else:
                    self.stdout.write(self.style.WARNING("Hozircha tekshiruvga tayyor target yo'q."))

                min_target_interval = MonitorTarget.objects.filter(is_active=True).aggregate(min_interval=Min("check_interval"))["min_interval"]
                sleep_seconds = max(5, min(interval, min_target_interval or interval))
                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Monitoring to'xtatildi."))
