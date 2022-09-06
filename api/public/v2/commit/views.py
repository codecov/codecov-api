from rest_framework import mixins

from api.shared.commit.mixins import CommitsViewSetMixin

from .serializers import CommitDetailSerializer, CommitSerializer


class CommitsViewSet(
    CommitsViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    def get_serializer_class(self):
        if self.action == "retrieve":
            return CommitDetailSerializer
        elif self.action == "list":
            return CommitSerializer
