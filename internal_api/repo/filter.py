from django.db.models import FloatField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django_filters import BooleanFilter
from django_filters import rest_framework as django_filters
from rest_framework import filters

from core.models import Repository


class StringListFilter(django_filters.Filter):
    def __init__(self, query_param, *args, **kwargs):
        super(StringListFilter, self).__init__(*args, **kwargs)
        self.query_param = query_param

    def filter(self, qs, value):
        try:
            request = self.parent.request
        except AttributeError:
            return None

        values = request.GET.getlist(self.query_param)
        if len(values) > 0:
            return qs.filter(**{"%s__%s" % (self.field_name, self.lookup_expr): values})

        return qs


class RepositoryFilters(django_filters.FilterSet):
    """Filter for active repositories"""

    active = BooleanFilter(field_name="active", method="filter_active")

    """Filter for getting multiple repositories by name"""
    names = StringListFilter(query_param="names", field_name="name", lookup_expr="in")

    def filter_active(self, queryset, name, value):
        # The database currently stores 't' instead of 'true' for active repos, and nothing for inactive
        # so if the query param active is set, we return repos with non-null value in active column
        return queryset.filter(active=value)

    class Meta:
        model = Repository
        fields = ["active", "names"]


class RepositoryOrderingFilter(filters.OrderingFilter):
    """
    Ordering filter that lazy-loads data into queryset
    when filtering on coverage metrics. This delays expensive queries
    so that they only slow down requests that require them.
    """

    def _order_by_totals_field(self, ordering_field, queryset):
        if ordering_field in ["coverage", "-coverage"]:
            annotation_args = dict(
                coverage=Cast(
                    KeyTextTransform("c", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        elif ordering_field in ["lines", "-lines"]:
            annotation_args = dict(
                lines=Cast(
                    KeyTextTransform("n", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        elif ordering_field in ["hits", "-hits"]:
            annotation_args = dict(
                hits=Cast(
                    KeyTextTransform("h", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        elif ordering_field in ["partials", "-partials"]:
            annotation_args = dict(
                partials=Cast(
                    KeyTextTransform("p", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        elif ordering_field in ["misses", "-misses"]:
            annotation_args = dict(
                misses=Cast(
                    KeyTextTransform("m", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        elif ordering_field in ["complexity", "-complexity"]:
            annotation_args = dict(
                complexity=Cast(
                    KeyTextTransform("C", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            )
        else:
            return queryset.order_by(ordering_field)

        return queryset.annotate(**annotation_args).order_by(ordering_field)

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            for ordering_field in ordering:
                queryset = self._order_by_totals_field(ordering_field, queryset)
        return queryset
