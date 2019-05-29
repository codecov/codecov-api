class RepoFilterMixin(object):

    def filter_queryset(self, queryset):
        repoid = self.kwargs.get('repoid')
        return queryset.filter(repository=repoid)
