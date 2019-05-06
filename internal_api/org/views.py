from rest_framework import generics
from internal_api.mixins import OwnerFilterMixin
from .serializers import OrgSerializer
from codecov_auth.models import Owner


class OrgsView(generics.ListCreateAPIView):
    queryset = Owner.objects.all()
    serializer_class = OrgSerializer