import logging

from django.utils.functional import cached_property
from django.shortcuts import get_object_or_404

from django.db.models import OuterRef, Exists, Func

from django.contrib.postgres.fields import ArrayField

from rest_framework import generics, viewsets, mixins, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from rest_framework.response import Response

from django_filters import rest_framework as django_filters

from codecov_auth.models import Owner, Service
from services.decorators import billing_safe
from services.billing import BillingService
from services.task import TaskService

from internal_api.mixins import OwnerPropertyMixin
from internal_api.permissions import UserIsAdminPermissions

from .serializers import (
    OwnerSerializer,
    AccountDetailsSerializer,
    UserSerializer,
    StripeInvoiceSerializer,
)

from .filters import UserFilters


log = logging.getLogger(__name__)


class ProfileView(generics.RetrieveAPIView):
    serializer_class = OwnerSerializer

    def get_object(self):
        return self.request.user


class OwnerViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin
):
    lookup_field = "username"
    serializer_class = OwnerSerializer

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
            username=self.kwargs.get("username"),
            service=self.kwargs.get("service")
        )

    @action(detail=True, methods=['get'])
    @billing_safe
    def invoices(self, request, *args, **kwargs):
        owner = self.get_object()
        if not owner.is_admin(self.request.user):
            raise PermissionDenied()
        return Response(
            StripeInvoiceSerializer(
                BillingService().list_invoices(owner, 100),
                many=True
            ).data
        )


class AccountDetailsViewSet(
    viewsets.GenericViewSet,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    OwnerPropertyMixin
):
    serializer_class = AccountDetailsSerializer
    permission_classes = [UserIsAdminPermissions]

    @billing_safe
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @billing_safe
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        TaskService().delete_owner(self.owner.ownerid)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self):
        return self.owner


class UserViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    OwnerPropertyMixin
):
    serializer_class = UserSerializer
    filter_backends = (django_filters.DjangoFilterBackend, filters.OrderingFilter,)
    filterset_class = UserFilters
    permission_classes = [UserIsAdminPermissions]
    ordering_fields = ('name',)
    lookup_field = "user_username"

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            username=self.kwargs.get("user_username")
        )

    def get_queryset(self):
        owner = self.owner
        if owner.has_legacy_plan:
            raise ValidationError(detail="Users API not accessible for legacy plans")
        return Owner.objects.filter(
            organizations__contains=[owner.ownerid]
        ).annotate(
            activated=Exists(
                Owner.objects.filter(
                    ownerid=owner.ownerid,
                    plan_activated_users__contains=Func(
                        OuterRef('ownerid'),
                        function='ARRAY',
                        template="%(function)s[%(expressions)s]"
                    )
                )
            ),
            is_admin=Exists(
                Owner.objects.filter(
                    ownerid=owner.ownerid,
                    admins__contains=Func(
                        OuterRef('ownerid'),
                        function='ARRAY',
                        template="%(function)s[%(expressions)s]"
                    )
                )
            )
        )
