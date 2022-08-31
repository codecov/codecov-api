from rest_framework import mixins

from api.shared.commit.mixins import CommitsViewSetMixin

from .serializers import CommitSerializer


class CommitsViewSet(CommitsViewSetMixin, mixins.ListModelMixin):
    serializer_class = CommitSerializer
