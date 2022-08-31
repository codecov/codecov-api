from rest_framework import mixins

from api.shared.branch.mixins import BranchViewSetMixin

from .serializers import BranchDetailSerializer, BranchSerializer


class BranchViewSet(
    BranchViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    def get_serializer_class(self):
        if self.action == "retrieve":
            return BranchDetailSerializer
        elif self.action == "list":
            return BranchSerializer
