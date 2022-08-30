from django.db.models import OuterRef, Subquery
from rest_framework import mixins

from api.shared.pull.mixins import PullViewSetMixin
from core.models import Commit

from .serializers import PullSerializer


class PullViewSet(
    PullViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = PullSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("author")
