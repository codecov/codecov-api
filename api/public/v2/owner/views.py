from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets

from api.public.v2.schema import owner_parameters
from api.shared.owner.mixins import OwnerViewSetMixin, UserViewSetMixin
from codecov_auth.models import Owner

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
