from django.db.models import OuterRef, Subquery
from rest_framework import mixins

from api.shared.branch.mixins import BranchViewSetMixin
from core.models import Commit

from .serializers import BranchSerializer


class BranchViewSet(BranchViewSetMixin, mixins.ListModelMixin):
    serializer_class = BranchSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                most_recent_commiter=Subquery(
                    Commit.objects.filter(
                        commitid=OuterRef("head"),
                        repository_id=OuterRef("repository__repoid"),
                    ).values("author__username")[:1]
                )
            )
        )
