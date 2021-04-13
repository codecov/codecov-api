from rest_framework import viewsets, mixins
from codecov_auth.models import Owner, Session
from internal_api.mixins import OwnerPropertyMixin
from internal_api.permissions import UserIsAdminPermissions

from .serializers import SessionSerializer, SessionWithTokenSerializer


class SessionViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    OwnerPropertyMixin,
):
    permission_classes = [UserIsAdminPermissions]

    def get_serializer_class(self):
        if self.action == "create":
            return SessionWithTokenSerializer
        return SessionSerializer

    def get_queryset(self):
        return Session.objects.filter(
            owner__ownerid__in=Owner.objects.users_of(owner=self.owner).values_list(
                "ownerid", flat=True
            )
        ).select_related("owner")
