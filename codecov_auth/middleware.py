import logging
from typing import Optional

from django.http import HttpRequest
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from rest_framework import exceptions

from codecov_auth.models import Owner, Service
from utils.services import get_long_service_name

log = logging.getLogger(__name__)


def get_service(request: HttpRequest) -> Optional[str]:
    resolver_match = resolve(request.path_info)
    service = resolver_match.kwargs.get("service")
    if service is not None:
        service = get_long_service_name(service.lower())
        try:
            Service(service)
            return service
        except ValueError:
            # not a valid service
            return None


class CurrentOwnerMiddleware(MiddlewareMixin):
    """
    The authenticated `User` may have multiple linked `Owners` and we need a way
    to load the "currently active" `Owner` for use in this request.

    If there's a `current_owner_id` value in the session then we use that.
    If the current owner does not match the request's `service` then we just pick the first
    of the user's owners with the matching service.

    This middleware is preferrable to accessing the session directly in views since
    we can load the `Owner` once and reuse it anywhere needed (without having to perform
    additional database queries).
    """

    def process_request(self, request):
        if not request.user or request.user.is_anonymous:
            request.current_owner = None
            return

        current_user = request.user
        current_owner = None

        current_owner_id = request.session.get("current_owner_id")
        if current_owner_id is not None:
            current_owner = current_user.owners.filter(pk=current_owner_id).first()

        service = get_service(request)
        if service and (current_owner is None or service != current_owner.service):
            # FIXME: this is OK (for now) since we're only allowing a single owner of a given
            # service to be linked to any 1 user
            current_owner = current_user.owners.filter(service=service).first()

        request.current_owner = current_owner


class ImpersonationMiddleware(MiddlewareMixin):
    """
    Allows staff users to impersonate other users for debugging.
    """

    def process_request(self, request):
        current_user = request.user

        if current_user and not current_user.is_anonymous:
            impersonating_ownerid = request.COOKIES.get("staff_user")
            if impersonating_ownerid is None:
                return

            log.info(
                "Impersonation attempted",
                extra=dict(
                    current_user_id=current_user.pk,
                    impersonating_ownerid=impersonating_ownerid,
                ),
            )
            if not current_user.is_staff:
                log.warning(
                    "Impersonation unsuccessful",
                    extra=dict(
                        reason="must be a staff user",
                        current_user_id=current_user.pk,
                        impersonating_ownerid=impersonating_ownerid,
                    ),
                )
                raise exceptions.PermissionDenied()

            request.current_owner = (
                Owner.objects.filter(pk=impersonating_ownerid)
                .prefetch_related("user")
                .first()
            )
            if request.current_owner is None:
                log.warning(
                    "Impersonation unsuccessful",
                    extra=dict(
                        reason="no such owner",
                        current_user_id=current_user.pk,
                        impersonating_ownerid=impersonating_ownerid,
                    ),
                )
                raise exceptions.AuthenticationFailed()

            log.info(
                "Impersonation successful",
                extra=dict(
                    current_user_id=current_user.pk,
                    impersonating_ownerid=impersonating_ownerid,
                ),
            )
