from typing import Any

from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.public.v2.schema import owner_parameters, service_parameter
from api.shared.owner.mixins import (
    OwnerViewSetMixin,
    UserSessionViewSetMixin,
    UserViewSetMixin,
)
from codecov_auth.models import Owner, Service

from .serializers import OwnerSerializer, UserSerializer, UserSessionSerializer


@extend_schema(parameters=owner_parameters, tags=["Users"])
class OwnerViewSet(
    OwnerViewSetMixin, viewsets.GenericViewSet, mixins.RetrieveModelMixin
):
    serializer_class = OwnerSerializer
    queryset = Owner.objects.none()

    @extend_schema(summary="Owner detail")
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Owner:
        """
        Returns a single owner by name
        """
        return super().retrieve(request, *args, **kwargs)


@extend_schema(parameters=owner_parameters, tags=["Users"])
class UserViewSet(UserViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = UserSerializer
    queryset = Owner.objects.none()

    @extend_schema(summary="User list")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns a paginated list of users for the specified owner (org)
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="User detail")
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Owner:
        """
        Returns a user for the specified owner_username or ownerid
        """
        return super().retrieve(request, *args, **kwargs)


@extend_schema(parameters=owner_parameters, tags=["Users"])
class UserSessionViewSet(UserSessionViewSetMixin, mixins.ListModelMixin):
    serializer_class = UserSessionSerializer
    queryset = Owner.objects.none()

    @extend_schema(summary="User session list")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns a paginated list of users' login session for the specified owner (org)
        """
        return super().list(request, *args, **kwargs)


@extend_schema(
    parameters=[
        service_parameter,
    ],
    tags=["Users"],
)
class OwnersViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = OwnerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet:
        service = self.kwargs.get("service")
        try:
            Service(service)
        except ValueError:
            raise NotFound(f"Service not found: {service}")

        current_owner = self.request.current_owner
        return Owner.objects.filter(
            Q(service=service, ownerid__in=current_owner.organizations)
            | Q(service=service, username=current_owner.username)
        )

    @extend_schema(summary="Service owners")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns all owners to which the currently authenticated user has access
        """
        return super().list(request, *args, **kwargs)
