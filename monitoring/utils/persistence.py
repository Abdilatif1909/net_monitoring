from monitoring.models import MonitoringResult



def save_monitoring_result(target, result_data: dict) -> MonitoringResult:
    result = MonitoringResult.objects.create(
        target=target,
        host=result_data.get("host", target.url),
        ip_address=result_data.get("ip_address"),
        status=result_data.get("status", target.last_status),
        ping_ms=result_data.get("ping_ms"),
        response_status_code=result_data.get("response_status_code"),
        response_time_ms=result_data.get("response_time_ms"),
        error_message=result_data.get("error_message", ""),
    )
    target.last_status = result.status
    target.save(update_fields=["last_status", "updated_at"])
    return result
