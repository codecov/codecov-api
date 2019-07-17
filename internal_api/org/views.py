from rest_framework import generics

from codecov_auth.models import Owner
from .serializers import OwnerSerializer


class OrgsView(generics.RetrieveAPIView):
    lookup_field = 'ownerid'
    queryset = Owner.objects.all()
    serializer_class = OwnerSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = queryset.get(ownerid=self.request.user.ownerid)
        return obj
