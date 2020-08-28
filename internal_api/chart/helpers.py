from django.db.models.functions import Trunc, Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import FloatField, Case, When, Value, Subquery, OuterRef
from rest_framework.exceptions import ValidationError
from cerberus import Validator


class ChartParamValidator(Validator):
    # Custom validation rule to require "agg_value" and "agg_function" fields only when not grouping by commit.
    # When grouping by commit, we return commits directly without applying any aggregation, so those fields aren't needed.
    def _validate_check_aggregation_fields(
        self, check_aggregation_fields, field, value
    ):
        agg_fields_present = self.document.get("agg_value") and self.document.get(
            "agg_function"
        )
        if check_aggregation_fields and value != "commit" and not agg_fields_present:
            self._error(
                field,
                "Must provide a value for agg_value and agg_function fields if not grouping by commit",
            )


def validate_params(data):
    """
    Explanation of parameters and how they impact the chart:

    - organization: username of the owner associated with the repositories/commits we're generating the chart for
    - repositories: indicates only commits in the list of repositories should be included. Note that the RepositoryChartHandler doesn't
    perform any aggregation if multiple repos are provided.
    - branch: indicates only commits in this branch should be included
    - start_date: indicates only commits after this date should be included
    - end_date: indicates only commits before this date should be included
    - grouping_unit: indicates how to group the commits. if this is 'commit' we'll just return ungrouped commits, if this is a unit of time
    (day, month, year) we'll group the commits by that time unit when applying aggregation.
    - agg_function: indicates how to aggregate the commits over . example: if this is 'max', we'll retrieve the commit within a time window with the
    highest value of whatever 'agg_value' is. *(See below for more explanation on this field)
    - agg_value: indicates which value we should perform aggregation/grouping on. example: if this is 'coverage', the aggregation function
    (min, max, etc.) will be applied to commit coverage. *(See below for more explanation on this field.)
    - coverage_timestamp_ordering: indicates in which order the coverage entries should be ordered by. Increasing will return the latest coverage
    at the end of the coverage array while decreasing will return the latest coverage at the beginning of the array.

    Aggregation fields - when grouping by a unit of time, we need to know which commit to retrieve over that unit of time - e.g. the latest commit
    in a given month, or the commit with the highest coverage, etc. The `agg_function` and `agg_value` parameters are used to determine this.
    Examples: { "grouping_unit": "month", "agg_function": "min", "agg_value": "coverage" } --> get the commit with the highest coverage in a given month
    Examples: { "grouping_unit": "week", "agg_function": "max", "agg_value": "timestmap" } --> get the most recent commit in a given week
    """

    params_schema = {
        "owner_username": {"type": "string", "required": True},
        "service": {"type": "string", "required": False},
        "repositories": {"type": "list"},
        "branch": {"type": "string"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "grouping_unit": {
            "type": "string",
            "required": True,
            "check_aggregation_fields": True,
            "allowed": [
                "commit",
                "hour",
                "day",
                "week",
                "month",
                "quarter",
                "year",
            ],  # must be one of the values accepted by Django's Trunc function; for more info see https://docs.djangoproject.com/en/3.0/ref/models/database-functions/#trunc
        },
        "agg_function": {"type": "string", "allowed": ["min", "max"],},
        "agg_value": {"type": "string", "allowed": ["timestamp", "coverage"]},
        "coverage_timestamp_ordering": {
            "type": "string",
            "allowed": ["increasing", "decreasing"],
        },
    }
    v = ChartParamValidator(params_schema)
    if not v.validate(data):
        raise ValidationError(v.errors)


def annotate_commits_with_totals(queryset):
    """
    Extract values from a commit's "totals" field and annotate the commit directly with those values.
    This is necessary when using Django aggregation functions, and otherwise is generally more convenient than wrangling with the totals JSON field.
    See "CommitTotalsSerializer" for reference on what the values ("c", "N", etc) represent
    """
    coverage = Cast(KeyTextTransform("c", "totals"), output_field=FloatField())
    lines = Cast(KeyTextTransform("n", "totals"), output_field=FloatField())
    hits = Cast(KeyTextTransform("h", "totals"), output_field=FloatField())
    misses = Cast(KeyTextTransform("m", "totals"), output_field=FloatField())
    partials = Cast(KeyTextTransform("p", "totals"), output_field=FloatField())

    complexity = Cast(KeyTextTransform("C", "totals"), FloatField()) or 0
    complexity_total = (
        Cast(KeyTextTransform("N", "totals"), output_field=FloatField()) or 0
    )

    return queryset.annotate(
        coverage=coverage,
        lines=lines,
        hits=hits,
        misses=misses,
        partials=partials,
        complexity=complexity,
        complexity_total=complexity_total,
        complexity_ratio=Case(
            When(complexity_total__gt=0, then=complexity / complexity_total),
            default=Value(0, output_field=FloatField()),
        ),
    )


def apply_grouping(queryset, data):
    """
    On the provided queryset, group commits by the time unit provided. Within each time window and for each repository represented in the
    given queryset, retrieve the appropriate commit based on the aggregation parameters (e.g. commit with "max" timestamp which will be the latest commit)
    See the params_schema in validate_params for info on the acceptable values here.
    """
    grouping_unit = data.get("grouping_unit")
    agg_function = data.get("agg_function")
    agg_value = data.get("agg_value")
    commit_order = data.get("coverage_timestamp_ordering", "increasing")

    # Truncate the commit's timestamp so we can group it in the appropriate time unit.
    # For example, if we're grouping by quarter, commits in Jan/Feb/March 2020 will all share the same truncated_date
    queryset = queryset.annotate(truncated_date=Trunc("timestamp", grouping_unit))
    date_ordering = "" if commit_order == "increasing" else "-"
    ordering = "" if agg_function == "min" else "-"
    return queryset.order_by(
        f"{date_ordering}truncated_date", "repository__name", f"{ordering}{agg_value}"
    ).distinct(
        "truncated_date", "repository__name"
    )  # this will select the first row for a given date/repo combo, which since we've just ordered the commits
    # should be the one with the min/max value we want to aggregate by


def aggregate_across_repositories(grouped_queryset):
    """
    Used for the organization analytics chart, which shows total sums across all repositories for a given time unit.
    The grouped_queryset has the approprate commit for each repo grouped by time unit, we'll aggregate this to get the sum and weighted average. 
    """
    result = []

    # Get the set of dates represented in the data, so we can retrieve the values for each repo within a given time window
    truncated_dates = grouped_queryset.distinct("truncated_date").values_list(
        "truncated_date", flat=True
    )

    for truncated_date in truncated_dates:
        commits = grouped_queryset.filter(truncated_date=truncated_date)

        # note: until we update to Django 3, can't call aggregate/annotate here or Django will freak out since we previously called "distinct" to group the queryset
        # see https://stackoverflow.com/questions/4048014/how-to-add-an-annotation-on-distinct-items
        total_lines = sum([commit.lines for commit in commits])
        total_hits = sum([commit.hits for commit in commits])
        total_partials = sum([commit.partials for commit in commits])
        total_misses = sum([commit.misses for commit in commits])

        weighted_coverage = (total_hits / total_lines) * 100

        result.append(
            {
                "date": truncated_date,
                "weighted_coverage": weighted_coverage,
                "total_lines": total_lines,
                "total_hits": total_hits,
                "total_partials": total_partials,
                "total_misses": total_misses,
            }
        )
    return result
