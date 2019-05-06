from rest_framework import generics

from internal_api.mixins import OwnerFilterMixin
from codecov_auth.models import Owner
from .serializers import OrgSerializer


class OrgsView(generics.ListCreateAPIView):
    queryset = Owner.objects.all()
    serializer_class = OrgSerializer

    def filter_queryset(self, queryset):
        ownerid = self.kwargs.get('ownerid')
        return queryset.filter(ownerid=ownerid)