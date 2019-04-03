import logging
log = logging.getLogger(__name__)

from .repo.models import Repository
from codecov_auth.models import Owner


class OwnerFilter(object):

    def filter_queryset(self, queryset):
        ownerid = self.kwargs.get('ownerid')

        if ownerid:
            return queryset.filter(author=ownerid)
        else:
            return queryset.all()


class RepoFilter(object):

    def filter_queryset(self, queryset):
        repoid = self.kwargs.get('repoid')

        if repoid:
            return queryset.filter(repository=repoid)
        else:
            return queryset.all()
