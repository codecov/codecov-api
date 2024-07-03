from django.db.models import Exists, OuterRef, Q
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
from .serializers import UserSerializer


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
        activated_owners = self_hosted.activated_owners()
        condition = (Q(oauth_token__isnull=False) & Q(organizations__isnull=False)) | Q(
            pk__in=activated_owners
        )
        return Owner.objects.filter(condition).annotate(
            is_admin=Coalesce(
                Exists(self_hosted.admin_owners().filter(pk=OuterRef("pk"))), False
            ),
            activated=Coalesce(
                Exists(activated_owners.filter(pk=OuterRef("pk"))),
                False,
            ),
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="current",
        permission_classes=[IsAuthenticated],
    )
    def current(self, request):
        current_owner = self.get_queryset().filter(pk=request.current_owner.pk).first()
        serializer = self.get_serializer(current_owner)
        return Response(serializer.data)

    @current.mapping.patch
    def current_update(self, request):
        current_owner = self.get_queryset().filter(pk=request.current_owner.pk).first()
        serializer = self.get_serializer(current_owner, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
