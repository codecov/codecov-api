import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from billing.constants import CURRENTLY_OFFERED_PLANS
from codecov_auth.models import Owner, Service
from internal_api.mixins import OwnerPropertyMixin
from internal_api.permissions import MemberOfOrgPermissions
from services.billing import BillingService
from services.decorators import stripe_safe
from services.segment import SegmentService
from services.task import TaskService

from .filters import UserFilters
from .serializers import (
    AccountDetailsSerializer,
    OwnerSerializer,
    StripeInvoiceSerializer,
    UserSerializer,
)

log = logging.getLogger(__name__)


class OwnerViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
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
            service=self.kwargs.get("service"),
        )


class InvoiceViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    OwnerPropertyMixin,
):
    serializer_class = StripeInvoiceSerializer
    permission_classes = [MemberOfOrgPermissions]
    pagination_class = None

    def get_queryset(self):
        return BillingService(requesting_user=self.request.user).list_invoices(
            self.owner, 100
        )

    def get_object(self):
        invoice_id = self.kwargs.get("pk")
        invoice = BillingService(requesting_user=self.request.user).get_invoice(
            self.owner, invoice_id
        )
        if not invoice:
            raise NotFound(f"Invoice {invoice_id} does not exist for that account")
        return invoice


class AccountDetailsViewSet(
    viewsets.GenericViewSet,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    OwnerPropertyMixin,
):
    serializer_class = AccountDetailsSerializer
    permission_classes = [MemberOfOrgPermissions]

    @stripe_safe
    def retrieve(self, *args, **kwargs):
        return super().retrieve(*args, **kwargs)

    @stripe_safe
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if self.owner.ownerid != request.user.ownerid:
            raise PermissionDenied("You can only delete your own account")

        SegmentService().account_deleted(self.owner)

        TaskService().delete_owner(self.owner.ownerid)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self):
        return self.owner

    @action(detail=False, methods=["patch"])
    @stripe_safe
    def update_payment(self, request, *args, **kwargs):
        payment_method = request.data.get("payment_method")
        if not payment_method:
            raise ValidationError(detail="No payment_method sent")
        owner = self.get_object()
        billing = BillingService(requesting_user=request.user)
        billing.update_payment_method(owner, payment_method)
        return Response(self.get_serializer(owner).data)


class UserViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    OwnerPropertyMixin,
):
    serializer_class = UserSerializer
    filter_backends = (
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    )
    filterset_class = UserFilters
    permission_classes = [MemberOfOrgPermissions]
    ordering_fields = ("name", "username", "email")
    lookup_field = "user_username_or_ownerid"
    search_fields = ["name", "username", "email"]

    def _base_queryset(self):
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
            self._base_queryset(),
            (Q(username=username_or_ownerid) | Q(ownerid=ownerid)),
        )

    def get_queryset(self):
        return self._base_queryset()


class PlanViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    def list(self, request, *args, **kwargs):
        return Response([val for key, val in CURRENTLY_OFFERED_PLANS.items()])
