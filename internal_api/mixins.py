class OwnerFilterMixin(object):

    def filter_queryset(self, queryset):
        ownerid = self.kwargs.get('ownerid')
        return queryset.filter(author=ownerid)


class RepoFilterMixin(object):

    def filter_queryset(self, queryset):
        repoid = self.kwargs.get('repoid')
        return queryset.filter(repository=repoid)
