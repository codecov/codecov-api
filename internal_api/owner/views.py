import logging

from django.utils.functional import cached_property
from django.shortcuts import get_object_or_404

from django.db.models import OuterRef, Exists, Func

from django.contrib.postgres.fields import ArrayField

from rest_framework import generics, viewsets, mixins, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError, NotAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from django_filters import rest_framework as django_filters

from codecov_auth.models import Owner, Service
from codecov_auth.constants import CURRENTLY_OFFERED_PLANS
from services.billing import BillingService
from services.task import TaskService
from services.segment import SegmentService

from internal_api.mixins import OwnerPropertyMixin
from internal_api.permissions import UserIsAdminPermissions

from .serializers import (
    ProfileSerializer,
    OwnerSerializer,
    AccountDetailsSerializer,
    UserSerializer,
    StripeInvoiceSerializer,
)

from .filters import UserFilters


log = logging.getLogger(__name__)


class ProfileViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin
):
    serializer_class = ProfileSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        raise NotAuthenticated()


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

class InvoiceViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    OwnerPropertyMixin
):
    serializer_class = StripeInvoiceSerializer
    permission_classes = [UserIsAdminPermissions]
    pagination_class = None

    def get_queryset(self):
        return BillingService(
            requesting_user=self.request.user
        ).list_invoices(self.owner, 100)

    def get_object(self):
        invoice_id = self.kwargs.get("pk")
        invoice = BillingService(
            requesting_user=self.request.user
        ).get_invoice(self.owner, invoice_id)
        if not invoice:
            raise NotFound(f"Invoice {invoice_id} does not exist for that account")
        return invoice


class AccountDetailsViewSet(
    viewsets.GenericViewSet,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    OwnerPropertyMixin
):
    serializer_class = AccountDetailsSerializer
    permission_classes = [UserIsAdminPermissions]

    def destroy(self, request, *args, **kwargs):
        if self.owner.ownerid != request.user.ownerid:
            raise PermissionDenied("You can only delete your own account")

        SegmentService().account_deleted(self.owner)

        TaskService().delete_owner(self.owner.ownerid)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self):
        return self.owner

    @action(detail=False, methods=['patch'])
    def update_payment(self, request, *args, **kwargs):
        payment_method = request.data.get("payment_method")
        if not payment_method:
            raise ValidationError(detail="No payment_method sent")
        owner = self.get_object()
        billing = BillingService(requesting_user=request.user)
        billing.update_payment_method(owner, payment_method)
        return Response(self.get_serializer(owner).data)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        response = super(StandardResultsSetPagination,
                         self).get_paginated_response(data)
        response.data['total_pages'] = self.page.paginator.num_pages
        return response


class UserViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    OwnerPropertyMixin
):
    serializer_class = UserSerializer
    filter_backends = (django_filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter)
    filterset_class = UserFilters
    permission_classes = [UserIsAdminPermissions]
    pagination_class = StandardResultsSetPagination
    ordering_fields = ('name', 'username', 'email')
    lookup_field = "user_username"
    search_fields = ['name', 'username', 'email']

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            username=self.kwargs.get("user_username")
        )

    def get_queryset(self):
        if self.owner.has_legacy_plan:
            raise ValidationError(detail="Users API not accessible for legacy plans")
        return Owner.objects.users_of(
            owner=self.owner
        ).annotate_activated_in(
            owner=self.owner
        ).annotate_is_admin_in(
            owner=self.owner
        ).annotate_with_latest_private_pr_date_in(
            owner=self.owner
        ).annotate_with_lastseen()


class PlanViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    def list(self, request, *args, **kwargs):
        return Response([val for key, val in CURRENTLY_OFFERED_PLANS.items()])
