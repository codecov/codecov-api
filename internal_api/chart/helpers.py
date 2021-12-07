from datetime import datetime

from cerberus import Validator
from dateutil import parser
from django.db import connection
from django.db.models import Case, F, FloatField, Value, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Trunc
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework.exceptions import ValidationError

from codecov_auth.models import Owner
from core.models import Commit, Repository


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
    complexity = Cast(KeyTextTransform("C", "totals"), FloatField()) or 0
    complexity_total = (
        Cast(KeyTextTransform("N", "totals"), output_field=FloatField()) or 0
    )
    return queryset.annotate(
        coverage=Cast(KeyTextTransform("c", "totals"), output_field=FloatField()),
        complexity=complexity,
        complexity_total=complexity_total,
        complexity_ratio=Case(
            When(complexity_total__gt=0, then=complexity / complexity_total),
            default=Value(None),
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


class ChartQueryRunner:
    """
    Houses the SQL query that retrieves data for analytics chart, and
    the associated parameter validation + transformation required for it.
    """

    def __init__(self, user, request_params):
        self.user = user
        self.request_params = request_params
        self._validate_parameters()

    def _dictfetchall(self, cursor):
        """
        Return all rows from a cursor as a dict
        Copied from: https://docs.djangoproject.com/en/3.1/topics/db/sql/#executing-custom-sql-directly
        """
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @property
    def start_date(self):
        """
        Lower bound on the date-range of commit data returned by query.
        Returns date of first commit made in any repo of 'repoids' is
        used if not set.
        """
        if "start_date" in self.request_params:
            return datetime.date(parser.parse(self.request_params.get("start_date")))
        return self.first_complete_commit_date

    @property
    def end_date(self):
        """
        Returns 'end_date' to use in date spine.
        """
        if "end_date" in self.request_params:
            return datetime.date(parser.parse(self.request_params.get("end_date")))
        return datetime.date(timezone.now())

    @property
    def interval(self):
        """
        Time interval between datapoints constructed in query.
        Derived from 'grouping_unit' request parameter.
        """
        if self.grouping_unit == "quarter":
            return "3 months"
        return f"1 {self.grouping_unit}"

    @property
    def grouping_unit(self):
        return self.request_params.get("grouping_unit")

    @property
    def ordering(self):
        """
        Data ordering is by ascending date, unless "decreasing" is
        supplied as ordering param.
        """
        if self.request_params.get("coverage_timestamp_ordering") == "decreasing":
            return "DESC"
        return ""

    @cached_property
    def repoids(self):
        """
        Returns a string of repoids of the repositories being queried.
        """
        organization = Owner.objects.get(
            service=self.request_params["service"],
            username=self.request_params["owner_username"],
        )

        # Get list of relevant repoids
        repos = Repository.objects.filter(author=organization).viewable_repos(self.user)

        if self.request_params.get("repositories", []):
            repos = repos.filter(name__in=self.request_params.get("repositories", []))

        if repos:
            # Get repoids into a format easily plugged into raw SQL
            return (
                "("
                + ",".join(map(str, list(repos.values_list("repoid", flat=True))))
                + ")"
            )

    @cached_property
    def first_complete_commit_date(self):
        """
        Date of first commit made to any repo in 'self.repoids'. Used as initial
        date for date_spine query.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH relevant_repo_branches AS (
                    SELECT
                        r.repoid,
                        r.branch
                    FROM repos r
                    WHERE r.repoid IN {self.repoids}
                )

                SELECT
                    DATE_TRUNC('{self.grouping_unit}', c.timestamp AT TIME ZONE 'UTC') as truncated_date
                FROM commits c
                INNER JOIN relevant_repo_branches r ON c.repoid = r.repoid AND c.branch = r.branch
                WHERE c.state = 'complete'
                ORDER BY c.timestamp ASC LIMIT 1;
                """
            )
            date = self._dictfetchall(cursor)

        if date:
            return datetime.date(date[0]["truncated_date"])

    def _validate_parameters(self):
        params_schema = {
            "owner_username": {"type": "string", "required": True},
            "service": {"type": "string", "required": True},
            "repositories": {"type": "list", "required": False},
            "start_date": {"type": "string", "required": False},
            "end_date": {"type": "string", "required": False},
            "agg_function": {"type": "string", "required": False},  # Deprecated
            "agg_value": {"type": "string", "required": False},  # Deprecated
            "grouping_unit": {
                "type": "string",
                "required": True,
                "allowed": [
                    "day",
                    "week",
                    "month",
                    "quarter",
                    "year",
                ],  # Must be one acceptable by Postgres DATE_TRUNC
            },
            "coverage_timestamp_ordering": {
                "type": "string",
                "allowed": ["increasing", "decreasing"],
                "required": False,
            },
        }
        v = Validator(params_schema)
        if not v.validate(self.request_params):
            raise ValidationError(v.errors)

    def run_query(self):
        # Edge cases -- no repos or no commits
        if not self.repoids:
            return []
        if not self.first_complete_commit_date:
            return []

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH date_series AS (
                    SELECT
                        t::date AS "date"
                    FROM generate_series(
                        timestamp '{self.first_complete_commit_date}',
                        timestamp '{self.end_date}',
                        '{self.interval}'
                    ) t
                ), graph_repos AS (
                    SELECT
                        r.repoid,
                        r.name,
                        r.branch
                    FROM
                        repos r
                    WHERE r.repoid IN {self.repoids}
                ), spine AS (
                    SELECT
                        ds.date,
                        r.repoid
                    FROM date_series ds
                    CROSS JOIN graph_repos r
                ), t_ranked_commits AS (
                    SELECT
                        ROW_NUMBER() OVER (
                            PARTITION BY c.repoid, DATE_TRUNC('{self.grouping_unit}', c.timestamp)
                            ORDER BY timestamp DESC NULLS LAST
                        ) AS commit_rank,
                        DATE_TRUNC('{self.grouping_unit}', c.timestamp) AS "truncated_date",
                        c.timestamp AS commit_timestamp,
                        c.totals,
                        r.repoid
                    FROM
                        commits c
                    INNER JOIN graph_repos r ON r.repoid = c.repoid
                        AND r.branch = c.branch
                        AND c.state = 'complete'
                ), commits_spine AS (
                    SELECT
                        s.date AS spine_date,
                        trc.truncated_date AS truncated_commit_date,
                        trc.commit_timestamp,
                        trc.totals AS totals,
                        s.repoid
                    FROM spine s
                    LEFT JOIN t_ranked_commits trc ON trc.truncated_date = s.date
                      AND trc.repoid = s.repoid
                      AND trc.commit_rank = 1
                ), grouped AS (
                    SELECT
                        spine_date,
                        truncated_commit_date,
                        totals,
                        repoid,
                        SUM(CASE
                            WHEN totals IS NOT NULL THEN 1 END
                        ) OVER (
                            PARTITION BY repoid
                            ORDER BY spine_date
                        ) AS grp_commit
                    FROM commits_spine
                ), corrected AS (
                    SELECT
                        spine_date,
                        FIRST_VALUE(totals) OVER (
                            PARTITION BY repoid, grp_commit
                            ORDER BY spine_date
                        ) AS corrected_totals
                    FROM
                        grouped
                ), parsed_totals AS (
                    SELECT
                        spine_date,
                        (CASE
                            WHEN corrected_totals IS NOT NULL then (corrected_totals->>'h')::numeric
                            WHEN corrected_totals IS NULL then 0 END
                        ) as hits,
                        (CASE
                            WHEN corrected_totals IS NOT NULL then (corrected_totals->>'m')::numeric
                            WHEN corrected_totals IS NULL then 0 END
                        ) as misses,
                        (CASE
                            WHEN corrected_totals IS NOT NULL then (corrected_totals->>'p')::numeric
                            WHEN corrected_totals IS NULL then 0 END
                        ) as partials,
                        (CASE
                            WHEN corrected_totals IS NOT NULL then (corrected_totals->>'n')::numeric
                            WHEN corrected_totals IS NULL then 0 END
                        ) as lines
                    FROM
                        corrected
                ), summed_totals AS (
                    SELECT
                        spine_date::timestamp at time zone 'UTC' AS date,
                        SUM(hits) AS total_hits,
                        SUM(misses) AS total_misses,
                        SUM(partials) AS total_partials,
                        SUM(lines) AS total_lines,
                        ROUND((SUM(hits) + SUM(partials)) / SUM(lines) * 100, 2) AS coverage
                    FROM
                        parsed_totals
                    GROUP BY spine_date
                    ORDER BY spine_date {self.ordering}
                )

                SELECT
                    *
                FROM summed_totals
                WHERE date >= DATE_TRUNC('{self.grouping_unit}', timestamp '{self.start_date}');
                """
            )

            return self._dictfetchall(cursor)
