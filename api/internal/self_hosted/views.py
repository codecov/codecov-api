from django.db.models import Exists, OuterRef
from django.db.models.functions import Coalesce
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import services.self_hosted as self_hosted
from codecov_auth.models import Owner

from .filters import UserFilters
from .permissions import AdminPermissions
from .serializers import SettingsSerializer, UserSerializer


class UserViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = UserSerializer
    filter_backends = (
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
    )
    filterset_class = UserFilters
    permission_classes = [AdminPermissions]
    ordering_fields = ("name", "username", "email")
    search_fields = ["name", "username", "email"]

    def get_queryset(self):
        return (
            Owner.objects.filter(oauth_token__isnull=False)
            .filter(organizations__isnull=False)
            .all()
            .annotate(
                is_admin=Coalesce(
                    Exists(self_hosted.admin_owners().filter(pk=OuterRef("pk"))), False
                ),
                activated=Coalesce(
                    Exists(self_hosted.activated_owners().filter(pk=OuterRef("pk"))),
                    False,
                ),
            )
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="current",
        permission_classes=[IsAuthenticated],
    )
    def current(self, request):
        current_user = self.get_queryset().filter(pk=request.user.pk).first()
        serializer = self.get_serializer(current_user)
        return Response(serializer.data)

    @current.mapping.patch
    def current_update(self, request):
        current_user = self.get_queryset().filter(pk=request.user.pk).first()
        serializer = self.get_serializer(current_user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SettingsViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = SettingsSerializer
    permission_classes = [AdminPermissions]

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self._get_settings())
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self._get_settings(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def _get_settings(self):
        return {
            "plan_auto_activate": self_hosted.is_autoactivation_enabled(),
            "seats_used": self_hosted.activated_owners().count(),
            "seats_limit": self_hosted.license_seats(),
        }
