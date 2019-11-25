
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from codecov_auth.models import Owner

from .serializers import AccountSerializer

class AccountViewSet(
        mixins.RetrieveModelMixin,
        mixins.UpdateModelMixin,
        viewsets.GenericViewSet
    ):
    queryset = Owner.objects.all()
    serializer_class = AccountSerializer
