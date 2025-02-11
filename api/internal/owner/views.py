import logging

from django.db.models import F
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from shared.django_apps.codecov_auth.models import Owner
from shared.plan.constants import DEFAULT_FREE_PLAN

from api.shared.mixins import OwnerPropertyMixin
from api.shared.owner.mixins import OwnerViewSetMixin, UserViewSetMixin
from api.shared.permissions import MemberOfOrgPermissions
from billing.helpers import on_enterprise_plan
from services.billing import BillingService
from services.decorators import stripe_safe
from services.task import TaskService

from .serializers import (
    AccountDetailsSerializer,
    OwnerSerializer,
    UserSerializer,
)

log = logging.getLogger(__name__)


class OwnerViewSet(OwnerViewSetMixin, mixins.RetrieveModelMixin):
    serializer_class = OwnerSerializer


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
        res = super().retrieve(*args, **kwargs)
        return res

    @stripe_safe
    def update(self, request, *args, **kwargs):
        # Temporary fix. Remove once Gazebo uses the new free plan
        plan_value = request.data.get("plan", {}).get("value")
        if plan_value == "users-basic":
            request.data["plan"]["value"] = DEFAULT_FREE_PLAN

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if self.owner.ownerid != request.current_owner.ownerid:
            raise PermissionDenied("You can only delete your own account")

        TaskService().delete_owner(self.owner.ownerid)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self):
        if self.owner.account:
            # gets the related account and invoice_billing objects from db in 1 query
            # otherwise, each reference to owner.account would be an additional query
            self.owner = (
                Owner.objects.filter(pk=self.owner.ownerid)
                .select_related("account__invoice_billing")
                .first()
            )
        return self.owner

    @action(detail=False, methods=["patch"])
    @stripe_safe
    def update_payment(self, request, *args, **kwargs):
        payment_method = request.data.get("payment_method")
        if not payment_method:
            raise ValidationError(detail="No payment_method sent")
        owner = self.get_object()
        billing = BillingService(requesting_user=request.current_owner)
        billing.update_payment_method(owner, payment_method)
        return Response(self.get_serializer(owner).data)

    @action(detail=False, methods=["patch"])
    @stripe_safe
    def update_email(self, request, *args, **kwargs):
        """
        Update the email address associated with the owner's billing account.

        Args:
            request: The HTTP request object containing:
                - new_email: The new email address to update to
                - apply_to_default_payment_method: Boolean flag to update email on the default payment method (default False)

        Returns:
            Response with serialized owner data

        Raises:
            ValidationError: If no new_email is provided in the request
        """
        new_email = request.data.get("new_email")
        if not new_email:
            raise ValidationError(detail="No new_email sent")
        owner = self.get_object()
        billing = BillingService(requesting_user=request.current_owner)
        apply_to_default_payment_method = request.data.get(
            "apply_to_default_payment_method", False
        )
        billing.update_email_address(
            owner,
            new_email,
            apply_to_default_payment_method=apply_to_default_payment_method,
        )
        return Response(self.get_serializer(owner).data)

    @action(detail=False, methods=["patch"])
    @stripe_safe
    def update_billing_address(self, request, *args, **kwargs):
        name = request.data.get("name")
        if not name:
            raise ValidationError(detail="No name sent")
        billing_address = request.data.get("billing_address")
        if not billing_address:
            raise ValidationError(detail="No billing_address sent")
        owner = self.get_object()

        formatted_address = {
            "line1": billing_address["line_1"],
            "line2": billing_address["line_2"],
            "city": billing_address["city"],
            "state": billing_address["state"],
            "postal_code": billing_address["postal_code"],
            "country": billing_address["country"],
        }

        billing = BillingService(requesting_user=request.current_owner)
        billing.update_billing_address(owner, name, billing_address=formatted_address)
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
            ordering += ["ownerid"]  # secondary sort column makes this deterministic
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
