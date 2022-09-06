import django_filters

from core.models import Commit


class CommitFilters(django_filters.FilterSet):
    branch = django_filters.CharFilter(field_name="branch", method="filter_branch")

    def filter_branch(self, queryset, name, value):
        return queryset.filter(branch=value)

    class Meta:
        model = Commit
        fields = ["branch"]
