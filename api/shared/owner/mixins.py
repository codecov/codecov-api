from django.db.models import BooleanField, Case, Max, Q, QuerySet, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, viewsets
from rest_framework.exceptions import NotFound

from api.shared.mixins import OwnerPropertyMixin
from api.shared.permissions import MemberOfOrgPermissions, UserIsAdminPermissions
from codecov_auth.models import Owner, Service

from .filters import UserFilters


class OwnerViewSetMixin(viewsets.GenericViewSet):
    lookup_field = "owner_username"
    lookup_value_regex = "[^/]+"

    def get_queryset(self) -> QuerySet:
        service = self.kwargs.get("service")
        try:
            Service(service)
        except ValueError:
            raise NotFound(f"Service not found: {service}")
        return Owner.objects.filter(service=self.kwargs.get("service"))

    def get_object(self) -> Owner:
        return get_object_or_404(
            self.get_queryset(),
            username=self.kwargs.get("owner_username"),
            service=self.kwargs.get("service"),
        )


class UserViewSetMixin(
    viewsets.GenericViewSet,
    OwnerPropertyMixin,
):
    filter_backends = (
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
    )
    filterset_class = UserFilters
    permission_classes = [MemberOfOrgPermissions]
    ordering_fields = ("name", "username", "email", "last_pull_timestamp", "activated")
    lookup_field = "user_username_or_ownerid"
    search_fields = ["name", "username", "email"]

    def get_queryset(self) -> QuerySet:
        return (
            Owner.objects.users_of(owner=self.owner)
            .annotate_activated_in(owner=self.owner)
            .annotate_is_admin_in(owner=self.owner)
        )

    def get_object(self) -> Owner:
        username_or_ownerid = self.kwargs.get("user_username_or_ownerid")
        try:
            ownerid = int(username_or_ownerid)
        except ValueError:
            ownerid = None

        return get_object_or_404(
            self.get_queryset(),
            (Q(username=username_or_ownerid) | Q(ownerid=ownerid)),
        )


class UserSessionViewSetMixin(
    viewsets.GenericViewSet,
    OwnerPropertyMixin,
):
    permission_classes = [UserIsAdminPermissions]
    ordering_fields = ("name", "username")

    def get_queryset(self) -> QuerySet:
        return Owner.objects.users_of(owner=self.owner).annotate(
            expiry_date=Max("session__login_session__expire_date"),
            has_active_session=Case(
                When(expiry_date__isnull=True, then=False),
                When(expiry_date__gt=timezone.now(), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )
