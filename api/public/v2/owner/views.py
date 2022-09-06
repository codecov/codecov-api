from rest_framework import mixins, viewsets

from api.shared.owner.mixins import OwnerViewSetMixin, UserViewSetMixin

from .serializers import OwnerSerializer, UserSerializer


class OwnerViewSet(
    OwnerViewSetMixin, viewsets.GenericViewSet, mixins.RetrieveModelMixin
):
    serializer_class = OwnerSerializer


class UserViewSet(
    UserViewSetMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = UserSerializer
