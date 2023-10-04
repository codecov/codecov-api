from typing import Optional

from django.http import HttpRequest
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

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
