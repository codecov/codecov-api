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

    # the filtering for these methods happens in the view since they
    # all need to be passed in to some of the timeseries helper functions

    def filter_interval(self, queryset, name, value):
        return queryset

    def filter_start_date(self, queryset, name, value):
        return queryset

    def filter_end_date(self, queryset, name, value):
        return queryset

    def filter_branch(self, queryset, name, value):
        return queryset
