import logging
import socket
import time
from urllib.parse import urlparse

import requests
from ping3 import ping

from monitoring.models import STATUS_OFFLINE, STATUS_ONLINE

logger = logging.getLogger(__name__)

ONLINE_HTTP_STATUS_CODES = {200, 301, 302}


def normalize_target_url(raw_target: str) -> str:
    if raw_target.startswith(("http://", "https://")):
        return raw_target
    return f"https://{raw_target}"


def extract_hostname(url: str) -> str:
    parsed = urlparse(normalize_target_url(url))
    return parsed.hostname or url


def resolve_ip_address(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        logger.warning("Failed to resolve IP address for host %s", host)
        return None


def ping_host(host: str, timeout: int) -> tuple[float | None, str]:
    try:
        ping_result = ping(host, timeout=timeout, unit="ms")
        if ping_result in (None, False):
            return None, f"Ping javobi yo'q: {host}"
        return round(float(ping_result), 2), ""
    except Exception as exc:
        logger.exception("Ping check failed for host %s", host)
        return None, str(exc)


def http_check(url: str, timeout: int) -> dict:
    normalized_url = normalize_target_url(url)
    started_at = time.perf_counter()
    try:
        response = requests.get(normalized_url, timeout=timeout, allow_redirects=False)
        response_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return {
            "response_status_code": response.status_code,
            "response_time_ms": response_time_ms,
            "http_online": response.status_code in ONLINE_HTTP_STATUS_CODES,
            "http_error": "" if response.status_code in ONLINE_HTTP_STATUS_CODES else f"HTTP {response.status_code}",
            "normalized_url": normalized_url,
        }
    except requests.RequestException as exc:
        logger.warning("HTTP check failed for %s: %s", normalized_url, exc)
        return {
            "response_status_code": None,
            "response_time_ms": None,
            "http_online": False,
            "http_error": str(exc),
            "normalized_url": normalized_url,
        }


def perform_hybrid_check(target, timeout: int) -> dict:
    host = extract_hostname(target.url)
    ip_address = resolve_ip_address(host)
    ping_ms, ping_error = ping_host(host, timeout)
    http_data = http_check(target.url, timeout)

    is_online = http_data["http_online"] or ping_ms is not None
    errors = [message for message in (ping_error, http_data["http_error"]) if message]

    return {
        "target": target,
        "host": http_data["normalized_url"],
        "ip_address": ip_address,
        "status": STATUS_ONLINE if is_online else STATUS_OFFLINE,
        "ping_ms": ping_ms,
        "response_status_code": http_data["response_status_code"],
        "response_time_ms": http_data["response_time_ms"],
        "error_message": "" if is_online else " | ".join(errors) or "Target javob bermadi.",
    }
