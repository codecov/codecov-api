import django_filters


class UserFilters(django_filters.FilterSet):
    activated = django_filters.BooleanFilter(
        method="filter_activated", label="activated"
    )
    is_admin = django_filters.BooleanFilter(method="filter_is_admin", label="is_admin")

    def filter_activated(self, queryset, name, value):
        return queryset.filter(activated=value)

    def filter_is_admin(self, queryset, name, value):
        return queryset.filter(is_admin=value)
