from typing import Optional

from django.http import HttpRequest
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django_prometheus.middleware import (
    Metrics,
    PrometheusAfterMiddleware,
    PrometheusBeforeMiddleware,
)

from utils.services import get_long_service_name


def get_service_long_name(request: HttpRequest) -> Optional[str]:
    resolver_match = resolve(request.path_info)
    service = resolver_match.kwargs.get("service")
    if service is not None:
        resolver_match.kwargs["service"] = get_long_service_name(service.lower())
        service = get_long_service_name(service.lower())
        return service
    return None


class ServiceMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        service = get_service_long_name(request)
        if service:
            view_kwargs["service"] = service
        return None


USER_AGENT_METRICS = [
    "django_http_requests_unknown_latency_including_middlewares_total",
    "django_http_requests_latency_seconds_by_view_method",
    "django_http_requests_unknown_latency_total",
    "django_http_ajax_requests_total",
    "django_http_requests_total_by_method",
    "django_http_requests_total_by_transport",
    "django_http_requests_total_by_view_transport_method",
    "django_http_requests_body_total_bytes",
    "django_http_responses_total_by_templatename",
    "django_http_responses_total_by_status",
    "django_http_responses_total_by_status_view_method",
    "django_http_responses_body_total_bytes",
    "django_http_responses_total_by_charset",
    "django_http_responses_streaming_total",
    "django_http_exceptions_total_by_type",
    "django_http_exceptions_total_by_view",
]


class CustomMetricsWithUA(Metrics):
    """
    Prometheus blah blah with user_agent header label
    """

    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        if name in USER_AGENT_METRICS:
            labelnames = list(labelnames) + ["user_agent"]
        return super().register_metric(
            metric_cls, name, documentation, labelnames=labelnames, **kwargs
        )


class AppMetricsBeforeMiddlewareWithUA(PrometheusBeforeMiddleware):
    """
    Prometheus blah blah but with user_agent header label
    """

    metrics_cls = CustomMetricsWithUA


class AppMetricsAfterMiddlewareWithUA(PrometheusAfterMiddleware):
    """
    Prometheus blah blah but with user_agent header label
    """

    metrics_cls = CustomMetricsWithUA

    def label_metric(self, metric, request, response=None, **labels):
        new_labels = labels
        if metric._name in USER_AGENT_METRICS:
            new_labels = {"user_agent": request.headers.get("User-Agent", "none")}
            new_labels.update(labels)
        return super().label_metric(metric, request, response=response, **new_labels)
