from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from api.public.v2.schema import owner_parameters, service_parameter
from api.shared.owner.mixins import OwnerViewSetMixin, UserViewSetMixin
from codecov_auth.models import Owner, Service

from .serializers import OwnerSerializer, UserSerializer


@extend_schema(parameters=owner_parameters, tags=["Users"])
class OwnerViewSet(
    OwnerViewSetMixin, viewsets.GenericViewSet, mixins.RetrieveModelMixin
):
    serializer_class = OwnerSerializer
    queryset = Owner.objects.none()

    @extend_schema(summary="Owner detail")
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single owner by name
        """
        return super().retrieve(request, *args, **kwargs)


@extend_schema(parameters=owner_parameters, tags=["Users"])
class UserViewSet(
    UserViewSetMixin,
    mixins.ListModelMixin,
):
    serializer_class = UserSerializer
    queryset = Owner.objects.none()

    @extend_schema(summary="User list")
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of users for the specified owner (org)
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

    def get_queryset(self):
        service = self.kwargs.get("service")
        try:
            Service(service)
        except ValueError:
            raise NotFound(f"Service not found: {service}")

        current_user = self.request.user
        return Owner.objects.filter(
            Q(service=service, ownerid__in=current_user.organizations)
            | Q(service=service, username=current_user.username)
        )

    @extend_schema(summary="Service owners")
    def list(self, request, *args, **kwargs):
        """
        Returns all owners to which the currently authenticated user has access
        """
        return super().list(request, *args, **kwargs)
