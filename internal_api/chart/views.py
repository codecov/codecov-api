from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser

from codecov_auth.models import Owner
from core.models import Commit
from .filters import apply_default_filters, apply_simple_filters
from .helpers import (
    annotate_commits_with_totals,
    apply_grouping,
    aggregate_across_repositories,
    validate_params,
)
from internal_api.permissions import ChartPermissions
from internal_api.mixins import RepositoriesMixin

from django.db import connection
from django.db.models import F
from django.db.models.functions import Trunc
from datetime import datetime


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict
    Copied from: https://docs.djangoproject.com/en/3.1/topics/db/sql/#executing-custom-sql-directly
    """
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


class RepositoryChartHandler(APIView, RepositoriesMixin):
    """
    Returns data used to populate the repository-level coverage chart. See "validate_params" for documentation on accepted parameters. 
    Can either group and aggregate commits by a unit of time, or just return latest commits from the repo within the given time frame.
    When aggregating by coverage, will also apply aggregation based on complexity ratio and return that.

    Responses take the following format (semantics of the response depend on whether we're grouping by time or not):     
    {
        "coverage": [
            {
                "date": "2019-06-01 00:00:00+00:00",
                    # grouping by time: NOT the commit timestamp, the date for this time window
                    # no grouping: when returning ungrouped commits: commit timestamp
                "coverage": <coverage value>
                    # grouping by time: coverage from the commit retrieved (the one with min/max coverage) for this time unit
                    # no grouping: coverage from the commit
                "commitid": <commitid>
                    # grouping by time: id of the commit retrieved (the one with min/max coverage) for this time unit
                    # no grouping: id of the commit
            },
            {
                "date": "2019-07-01 00:00:00+00:00",
                "coverage": <coverage value>
                "commitid": <commit id>
                ...
            },
            ...
        ],
        "complexity": [
            {
                "date": "2019-07-01 00:00:00+00:00",
                "complexity_ratio": <complexity ratio value>
                "commitid": <commit id>
            },
            {
                "date": "2019-07-01 00:00:00+00:00",     
                ...   
            },
            ...
        ]
    }
    """

    permission_classes = [ChartPermissions]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        request_params = {**self.request.data, **self.kwargs}
        validate_params(request_params)
        coverage_ordering = "" if request_params.get("coverage_timestamp_order", "increasing") == "increasing" else "-"

        queryset = apply_simple_filters(
            apply_default_filters(Commit.objects.all()), request_params, self.request.user
        )

        annotated_queryset = annotate_commits_with_totals(queryset)

        # if grouping_unit doesn't specify time, return all values
        if self.request.data.get("grouping_unit") == "commit":
            max_num_commits = 1000
            commits = annotated_queryset.order_by(f"{coverage_ordering}timestamp")[:max_num_commits]
            coverage = [
                {
                    "date": commits[index].timestamp,
                    "coverage": commits[index].coverage,
                    "coverage_change": commits[index].coverage -
                                       commits[max(index - 1, 0)].coverage,
                    "commitid": commits[index].commitid,
                }
                for index in range(len(commits))
            ]

            complexity = [
                {
                    "date": commit.timestamp,
                    "complexity_ratio": commit.complexity_ratio,
                    "commitid": commit.commitid,
                }
                for commit in annotated_queryset.order_by(f"{coverage_ordering}timestamp")[:max_num_commits] if commit.complexity_ratio is not None
            ]

        else:
            # Coverage
            coverage_grouped_queryset = apply_grouping(
                annotated_queryset, self.request.data
            )

            commits = coverage_grouped_queryset
            coverage = [
                {
                    "date": commits[index].truncated_date,
                    "coverage": commits[index].coverage,
                    "coverage_change": commits[index].coverage -
                                       commits[max(index - 1, 0)].coverage,
                    "commitid": commits[index].commitid,
                }
                for index in range(len(commits))
            ]

            # Complexity
            complexity_params = self.request.data.copy()
            complexity_params["agg_value"] = "complexity_ratio"
            complexity_grouped_queryset = apply_grouping(
                annotated_queryset, complexity_params
            )
            complexity = [
                {
                    "date": commit.truncated_date,
                    "complexity_ratio": commit.complexity_ratio,
                    "commitid": commit.commitid,
                }
                for commit in complexity_grouped_queryset if commit.complexity_ratio is not None
            ]

        return Response(data={"coverage": coverage, "complexity": complexity})


class OrganizationChartHandler(APIView, RepositoriesMixin):
    """
    Returns data used to populate the organization-level analytics chart. See "validate_params" for documentation on accepted parameters. 
    Functions generally similarly to the repository chart, with a few exceptions: aggregates coverage across multiple repositories, 
    doesn't return complexity, and doesn't support retrieving a list of commits (so coverage must be grouped by a unit of time).

    Responses take the following format: (example assumes grouping by month)
    {
        "coverage": [
            {
                "date": "2019-06-01 00:00:00+00:00", <NOT the commit timestamp, the date for the time window>
                "coverage": <coverage calculated by taking (total_lines + total_hits) / total_partials>,
                "total_lines": <sum of lines across repositories from the commit we retrieved for the repo>,
                "total_hits": <sum of hits across repositories>,
                "total_partials": <sum of partials across repositories>,
            },
            {
                "date": "2019-07-01 00:00:00+00:00",
                ...
            },
            ...
        ]
    }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        request_params = {**self.request.data, **self.kwargs}
        validate_params(request_params)

        organization = Owner.objects.get(service=kwargs["service"], username=kwargs["owner_username"])
        viewable_repoid_set = organization.repository_set.viewable_repos(request.user).values_list("repoid", flat=True)

        # determine start date to use
        if "start_date" in request_params:
            start_date = parser.parse(request_params.get("start_date"))
        else:
            first_commit_date = Commit.objects.filter(
                repository__repoid__in=viewable_repoid_set,
                repository__branch=F('branch')
            ).annotate(
                truncated_date=Trunc('timestamp', request_params.get("grouping_unit"))
            ).order_by('-timestamp').values_list('truncated_date', flat=True)[0]

            start_date = datetime.date(first_commit_date)

        # determine end date to use
        if "end_date" in request_params:
            end_date = parser.parse(request_params.get("end_date"))
        else:
            end_date = datetime.date(datetime.now())

        with connection.cursor() as cursor:
            result = cursor.execute(
                """
                WITH date_series AS (
                	SELECT
                		t::date AS "date"
                	FROM generate_series(timestamp '{start_date}', timestamp '{end_date}', '1 {grouping_unit}') t
                ), graph_repos AS (
                	SELECT
                		r.repoid,
                		r.name,
                        r.branch
                	FROM 
                		repos r
                	WHERE r.repoid IN {viewable_repoid_set}
                ), spine AS (
                    SELECT
                        ds.date,
                        r.repoid
                    FROM date_series ds
                    CROSS JOIN graph_repos r
                ), t_ranked_commits AS (
                	SELECT
                		ROW_NUMBER() OVER (PARTITION BY c.repoid, DATE_TRUNC('{grouping_unit}', c.timestamp) ORDER BY timestamp DESC NULLS LAST) AS commit_rank,
                		DATE_TRUNC('{grouping_unit}', c.timestamp) AS "truncated_date",
                		c.timestamp AS commit_timestamp,
                		c.id,
                		r.repoid
                	FROM
                		commits c
                	INNER JOIN graph_repos r ON r.repoid = c.repoid AND r.branch = c.branch
                ), commits_spine AS (
                	SELECT 
                		s.date AS spine_date,
                		drc.truncated_date AS truncated_commit_date,
                		drc.commit_timestamp,
                		drc.id AS commit_id,
                		s.repoid
                	FROM spine s
                	LEFT JOIN t_ranked_commits drc ON drc.truncated_date = s.date AND drc.repoid = s.repoid AND drc.commit_rank = 1
                ), grouped AS (
                	SELECT
                		spine_date,
                		truncated_commit_date,
                		commit_id,
                		repoid,
                		SUM(CASE WHEN commit_id IS NOT NULL THEN 1 END) OVER (PARTITION BY repoid ORDER BY spine_date) AS grp_commit
                    FROM commits_spine
                ), corrected AS (
                	SELECT
                	  	spine_date,
                	    truncated_commit_date,
                	    commit_id, 
                	    FIRST_VALUE(commit_id) OVER (PARTITION BY repoid, grp_commit ORDER BY spine_date) AS corrected_commit
                	FROM
                		grouped
                )
                SELECT
                	spine_date::timestamp at time zone 'UTC' AS date,
                	SUM((c.totals->>'h')::numeric) AS total_hits,
                	SUM((c.totals->>'m')::numeric) AS total_misses,
                	SUM((c.totals->>'p')::numeric) AS total_partials,
                	SUM((c.totals->>'n')::numeric) AS total_lines,
                    SUM((c.totals->>'h')::numeric) / SUM((c.totals->>'n')::numeric) * 100 AS coverage
                FROM
                	corrected
                LEFT JOIN commits c ON c.id = corrected_commit
                GROUP BY spine_date
                ORDER BY spine_date {ordering_param};
                """.format(
                    start_date=start_date,
                    end_date=end_date,
                    grouping_unit=request_params.get("grouping_unit"),
                    viewable_repoid_set=tuple(viewable_repoid_set),
                    ordering_param="DESC" if request_params.get("coverage_timestamp_ordering") == "decreasing" else ""
                )
            )

            return Response(
                data={
                    "coverage": dictfetchall(cursor)
                }
            )
