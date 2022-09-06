from django.db.models import FloatField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from rest_framework import filters


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
