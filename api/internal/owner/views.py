import logging

from django.db.models import F
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from api.shared.mixins import OwnerPropertyMixin
from api.shared.owner.mixins import OwnerViewSetMixin, UserViewSetMixin
from api.shared.permissions import MemberOfOrgPermissions
from billing.constants import CURRENTLY_OFFERED_PLANS
from billing.helpers import on_enterprise_plan
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


class OwnerViewSet(OwnerViewSetMixin, mixins.RetrieveModelMixin):
    serializer_class = OwnerSerializer


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


class UsersOrderingFilter(filters.OrderingFilter):
    def get_valid_fields(self, queryset, view, context=None):
        fields = super().get_valid_fields(queryset, view, context=context or {})

        if "last_pull_timestamp" not in queryset.query.annotations:
            # queryset not always annotated with `last_pull_timestamp`
            fields = [
                (name, verbose_name)
                for (name, verbose_name) in fields
                if name != "last_pull_timestamp"
            ]

        return fields

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            ordering = [self._order_expression(order) for order in ordering]
            return queryset.order_by(*ordering)

        return queryset

    def _order_expression(self, order):
        """
        Special cases for `last_pull_timestamp`:
        - nulls first when ascending
        - nulls last when descending
        """
        if order == "last_pull_timestamp":
            return F("last_pull_timestamp").asc(nulls_first=True)
        elif order == "-last_pull_timestamp":
            return F("last_pull_timestamp").desc(nulls_last=True)
        else:
            return order


class UserViewSet(
    UserViewSetMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = UserSerializer
    filter_backends = (
        django_filters.DjangoFilterBackend,
        UsersOrderingFilter,
        filters.SearchFilter,
    )

    def get_queryset(self):
        qs = super().get_queryset()
        if on_enterprise_plan(self.owner):
            # pull ordering only available for enterprise
            qs = qs.annotate_last_pull_timestamp()
        return qs


class PlanViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    def list(self, request, *args, **kwargs):
        return Response([val for key, val in CURRENTLY_OFFERED_PLANS.items()])
