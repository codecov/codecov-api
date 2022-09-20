from rest_framework import mixins

from api.shared.compare.mixins import CompareViewSetMixin

from .serializers import ComparisonSerializer


class CompareViewSet(
    CompareViewSetMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = ComparisonSerializer
