import django_filters


class MeasurementFilters(django_filters.FilterSet):
    start_date = django_filters.DateTimeFilter(
        label="start date/time (inclusive)", method="filter_start_date"
    )
    end_date = django_filters.DateTimeFilter(
        label="end date/time (inclusive)", method="filter_end_date"
    )
    branch = django_filters.CharFilter(label="branch name", method="filter_branch")

    def filter_start_date(self, queryset, name, value):
        return queryset.filter(timestamp_bin__gte=value)

    def filter_end_date(self, queryset, name, value):
        return queryset.filter(timestamp_bin__lte=value)

    def filter_branch(self, queryset, name, value):
        return queryset.filter(branch=value)
