from rest_framework import generics

from codecov_auth.models import Owner
from .serializers import OwnerListSerializer


class OrgsView(generics.RetrieveAPIView):
    lookup_field = 'ownerid'
    queryset = Owner.objects.all()
    serializer_class = OwnerListSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = queryset.get(ownerid=self.request.user.ownerid)
        return obj
