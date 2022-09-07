import django_filters

INTERVAL_CHOICES = (
    ("1d", "1 day"),
    ("7d", "7 day"),
    ("30d", "30 day"),
)


class MeasurementFilters(django_filters.FilterSet):
    interval = django_filters.ChoiceFilter(
        choices=INTERVAL_CHOICES, method="filter_interval", required=True
    )
    start_date = django_filters.DateTimeFilter(
        label="start datetime (inclusive)", method="filter_start_date"
    )
    end_date = django_filters.DateTimeFilter(
        label="end datetime (inclusive)", method="filter_end_date"
    )
    branch = django_filters.CharFilter(label="branch name", method="filter_branch")

    def filter_interval(self, queryset, name, value):
        # the filtering for this method happens in the view since it
        # delegates to different underlying models
        return queryset

    def filter_start_date(self, queryset, name, value):
        return queryset.filter(timestamp_bin__gte=value)

    def filter_end_date(self, queryset, name, value):
        return queryset.filter(timestamp_bin__lte=value)

    def filter_branch(self, queryset, name, value):
        return queryset.filter(branch=value)
