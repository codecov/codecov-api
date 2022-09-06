from django.db.models import F, OuterRef, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from api.shared.branch.mixins import BranchViewSetMixin
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from core.models import Branch, Commit

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
