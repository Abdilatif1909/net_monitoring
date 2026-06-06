from django.conf import settings
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from monitoring.alerts.notifier import send_offline_notifications
from monitoring.models import MonitorTarget, MonitoringResult, NotificationHistory, STATUS_OFFLINE, STATUS_ONLINE


class MonitoringPlatformTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username="tester", password="secret123")
		self.target = MonitorTarget.objects.create(
			name="Example",
			url="https://example.com",
			is_active=True,
			check_interval=30,
			last_status=STATUS_ONLINE,
		)
		MonitoringResult.objects.create(
			target=self.target,
			host="example.com",
			status=STATUS_ONLINE,
			ping_ms=12.4,
			response_status_code=200,
			response_time_ms=101.2,
		)
		MonitoringResult.objects.create(
			target=self.target,
			host="example.com",
			status=STATUS_OFFLINE,
			error_message="Timeout",
		)

	def test_health_endpoint_returns_ok(self):
		response = self.client.get(reverse("monitoring:health"))
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["app_status"], "ok")
		self.assertEqual(payload["db_status"], "ok")

	@patch("monitoring.views.run_due_targets_monitoring")
	def test_dashboard_partial_returns_html_fragments(self, mocked_run_due):
		mocked_run_due.return_value = {"results": [], "items": []}
		self.client.login(username="tester", password="secret123")

		response = self.client.get(reverse("monitoring:dashboard-partial"))
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn("widgets_html", payload)
		self.assertIn("targets_html", payload)
		self.assertIn("charts", payload)

	def test_target_statistics_json_export(self):
		self.client.login(username="tester", password="secret123")
		response = self.client.get(
			reverse("monitoring:target-export", kwargs={"pk": self.target.pk}),
			{"type": "statistics", "format": "json"},
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["target"], self.target.name)
		self.assertIn("daily_uptime", payload)

	@patch("monitoring.views.run_monitoring_for_target")
	def test_target_check_page_renders_html_dashboard(self, mocked_run_monitoring):
		latest_result = self.target.results.first()
		mocked_run_monitoring.return_value = {
			"result": latest_result,
			"status_changed": False,
			"notification_sent": False,
			"email_sent": False,
		}
		self.client.login(username="tester", password="secret123")

		response = self.client.get(reverse("monitoring:target-check", kwargs={"target_id": self.target.pk}))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.target.name)
		self.assertContains(response, "Recent checks")

	@patch("monitoring.views.run_monitoring_for_target")
	def test_monitor_prefixed_target_check_page_renders(self, mocked_run_monitoring):
		latest_result = self.target.results.first()
		mocked_run_monitoring.return_value = {
			"result": latest_result,
			"status_changed": False,
			"notification_sent": False,
			"email_sent": False,
		}
		self.client.login(username="tester", password="secret123")

		response = self.client.get(reverse("monitoring:monitor-target-check", kwargs={"target_id": self.target.pk}))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "target-check-live-root")

	@patch("monitoring.views.run_monitoring_for_target")
	def test_target_check_live_data_returns_ajax_payload(self, mocked_run_monitoring):
		latest_result = self.target.results.first()
		mocked_run_monitoring.return_value = {
			"result": latest_result,
			"status_changed": False,
			"notification_sent": False,
			"email_sent": False,
		}
		self.client.login(username="tester", password="secret123")

		response = self.client.get(reverse("monitoring:target-check-live-data", kwargs={"target_id": self.target.pk}))
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn("html", payload)
		self.assertIn("charts", payload)
		self.assertEqual(payload["status"], latest_result.status)

	@patch("monitoring.views.send_test_telegram_alert", return_value=True)
	def test_monitor_telegram_test_page_renders(self, mocked_send):
		self.client.login(username="tester", password="secret123")
		response = self.client.get(reverse("monitoring:monitor-telegram-test"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Telegram connected")
		self.assertTrue(mocked_send.called)

	def test_monitor_target_check_missing_target_returns_404_page(self):
		self.client.login(username="tester", password="secret123")
		response = self.client.get(reverse("monitoring:monitor-target-check", kwargs={"target_id": 99999}))
		self.assertEqual(response.status_code, 404)
		self.assertContains(response, "Target topilmadi", status_code=404)

	def test_rest_framework_uses_json_renderer_only(self):
		self.assertEqual(
			settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"],
			["rest_framework.renderers.JSONRenderer"],
		)

	@patch("monitoring.alerts.notifier.internet_offline_alert", return_value=True)
	@patch("monitoring.alerts.notifier.internet_offline_email_alert", return_value=True)
	def test_notification_history_created_for_offline_alerts(self, mocked_email, mocked_telegram):
		result = MonitoringResult.objects.create(
			target=self.target,
			host="example.com",
			status=STATUS_OFFLINE,
			error_message="Offline",
		)

		send_offline_notifications(result, severity="warning")

		self.assertEqual(NotificationHistory.objects.filter(target=self.target).count(), 2)
		self.assertTrue(mocked_telegram.called)
		self.assertTrue(mocked_email.called)
