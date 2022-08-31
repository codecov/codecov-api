from django.db.models import OuterRef, Subquery
from rest_framework import mixins

from api.shared.pull.mixins import PullViewSetMixin
from core.models import Commit

from .serializers import PullDetailSerializer, PullSerializer


class PullViewSet(
    PullViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    def get_serializer_class(self):
        if self.action == "retrieve":
            return PullDetailSerializer
        elif self.action == "list":
            return PullSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                most_recent_commiter=Subquery(
                    Commit.objects.filter(
                        commitid=OuterRef("head"), repository=OuterRef("repository")
                    ).values("author__username")[:1]
                ),
            )
        )
