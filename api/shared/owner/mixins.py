from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as django_filters
from rest_framework import filters, viewsets
from rest_framework.exceptions import NotFound

from api.shared.mixins import OwnerPropertyMixin
from api.shared.permissions import MemberOfOrgPermissions
from codecov_auth.models import Owner, Service

from .filters import UserFilters


class OwnerViewSetMixin(viewsets.GenericViewSet):
    lookup_field = "owner_username"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        service = self.kwargs.get("service")
        try:
            Service(service)
        except ValueError:
            raise NotFound(f"Service not found: {service}")
        return Owner.objects.filter(service=self.kwargs.get("service"))

    def get_object(self):
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

    def get_queryset(self):
        return (
            Owner.objects.users_of(owner=self.owner)
            .annotate_activated_in(owner=self.owner)
            .annotate_is_admin_in(owner=self.owner)
        )

    def get_object(self):
        username_or_ownerid = self.kwargs.get("user_username_or_ownerid")
        try:
            ownerid = int(username_or_ownerid)
        except ValueError:
            ownerid = None

        return get_object_or_404(
            self.get_queryset(),
            (Q(username=username_or_ownerid) | Q(ownerid=ownerid)),
        )
