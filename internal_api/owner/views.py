import logging

from django.shortcuts import get_object_or_404
from django.db.models import Subquery, OuterRef, Q

from rest_framework import generics, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response

from codecov_auth.models import Owner, Service
from services.decorators import billing_safe

from .serializers import (
    OwnerSerializer,
    AccountDetailsSerializer
)


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

    @action(detail=True, methods=['get'], url_path="account-details")
    @billing_safe
    def account_details(self, request, *args, **kwargs):
        owner = self.get_object()
        if not owner.is_admin(self.request.user):
            raise PermissionDenied()
        return Response(AccountDetailsSerializer(owner).data)
