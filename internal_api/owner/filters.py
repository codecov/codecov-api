import django_filters


class UserFilters(django_filters.FilterSet):
    activated = django_filters.BooleanFilter(method='filter_activated')
    prefix = django_filters.CharFilter(method="filter_prefix")

    def filter_activated(self, queryset, name, value):
        return queryset.filter(activated=value)

    def filter_prefix(self, queryset, name, value):
        return queryset.filter(name__istartswith=value)
