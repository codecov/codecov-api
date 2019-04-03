from rest_framework import generics
from internal_api.views import RepoFilter
from .models import Pull
from .serializers import PullSerializer


class RepoPullsView(RepoFilter, generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer