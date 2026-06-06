# Online Net Monitoring Platform

Professional Django-based monitoring platform for tracking multiple websites with hybrid ping + HTTP checks, smart alerts, analytics, filtering, exports, and realtime dashboard updates.

## Muallif

- Dilmurod O'roqov
- Axborot texnologiyalari va mmenejment universiteti magistranti
- Telefon: +998 90 518 84 42
- Telegram: @Dilmurod_TUIT
- Email: Dilmurod123@gmail.com
- Loyiha ichidagi muallif rasmi: [static/img/author-avatar.svg](static/img/author-avatar.svg)

## Features

- Multi-target monitoring
- Hybrid ping + HTTP availability checks
- Realtime dashboard partial refresh
- Smart alerting with consecutive failure threshold and cooldown
- Telegram and email notifications
- Notification history tracking
- Target detail analytics
- CSV and JSON exports
- Health endpoint
- Dark mode toggle
- Django admin integration
- Authentication-protected dashboard
- File logging and in-memory caching

## Tech Stack

- Django
- Django REST Framework
- SQLite
- Bootstrap 5
- Chart.js
- ping3
- requests
- python-decouple

## Project Structure

- [config/settings.py](config/settings.py) — Django settings, cache, logging, alert configuration
- [monitoring/models.py](monitoring/models.py) — targets, results, state, notification history
- [monitoring/views.py](monitoring/views.py) — dashboard, partial refresh, exports, health, target detail
- [monitoring/services/monitoring.py](monitoring/services/monitoring.py) — monitoring workflow and smart alert logic
- [monitoring/services/checks.py](monitoring/services/checks.py) — ping and HTTP checks
- [monitoring/alerts/notifier.py](monitoring/alerts/notifier.py) — multi-channel notifications
- [monitoring/analytics/service.py](monitoring/analytics/service.py) — dashboard and target analytics
- [monitoring/templates/monitoring/dashboard.html](monitoring/templates/monitoring/dashboard.html) — main dashboard UI

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Configure environment variables in `.env`.
4. Run migrations:
   - `python manage.py migrate`
5. Create a superuser if needed:
   - `python manage.py createsuperuser`
6. Start the server:
   - `python manage.py runserver`
7. Start background monitoring loop in a second terminal:
   - `python manage.py start_monitoring`

## Important Environment Variables

Example values should be placed in `.env`.

- `SECRET_KEY`
- `DEBUG`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `ALERT_EMAIL_RECIPIENTS`
- `MONITOR_TIMEOUT`
- `MONITOR_INTERVAL_SECONDS`
- `ALERT_CONSECUTIVE_FAILURES`
- `ALERT_COOLDOWN_SECONDS`

## Key Endpoints

- `/` — Dashboard
- `/dashboard/partial/` — Partial realtime dashboard payload
- `/targets/` — Target list
- `/targets/<id>/` — Target detail and analytics
- `/targets/<id>/export/?type=history&format=csv` — Target export
- `/health/` — Health check
- `/api/check/` — Check due targets
- `/api/check/<id>/` — Force single target check
- `/api/results/` — Monitoring results API

## Smart Alerting Rules

- Alert after configured consecutive failures
- Cooldown prevents repeated spam
- Severity escalates from `warning` to `critical`
- Recovery notifications are sent when a target returns online
- Every notification is written to notification history

## Logging

Logs are written into the `logs/` directory:

- `monitoring.log`
- `alerts.log`
- `errors.log`

## Testing

Run tests with:

- `python manage.py test`

Current tests cover:

- Health endpoint
- Partial dashboard endpoint
- Export endpoint
- Notification history persistence

## Notes

- Dashboard partial refresh avoids full page reload.
- SQLite is suitable for development and demos.
- For production, switch to PostgreSQL and run monitoring with a proper scheduler or worker.
