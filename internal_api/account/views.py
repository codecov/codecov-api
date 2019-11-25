from rest_framework import viewsets

from codecov_auth.models import Owner

class AccountViewSet(viewsets.GenericViewSet):
    queryset = Owner.objects.all()
