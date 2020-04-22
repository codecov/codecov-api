import django_filters


class BranchFilters(django_filters.FilterSet):
    author = django_filters.CharFilter(method='filter_author')

    def filter_author(self, queryset, name, value):
        return queryset.filter(authors__contains=[value])
