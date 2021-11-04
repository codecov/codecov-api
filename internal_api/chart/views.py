from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from core.models import Commit
from internal_api.mixins import OwnerPropertyMixin, RepositoriesMixin
from internal_api.permissions import ChartPermissions

from .filters import apply_default_filters, apply_simple_filters
from .helpers import (
    ChartQueryRunner,
    annotate_commits_with_totals,
    apply_grouping,
    validate_params,
)


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
        coverage_ordering = (
            ""
            if request_params.get("coverage_timestamp_order", "increasing")
            == "increasing"
            else "-"
        )

        # We don't use the "report" field in this endpoint and it can be many MBs of JSON choosing not to
        # fetch it for perf reasons
        queryset = apply_simple_filters(
            apply_default_filters(Commit.objects.defer("report").all()),
            request_params,
            self.request.user,
        )

        annotated_queryset = annotate_commits_with_totals(queryset)

        # if grouping_unit doesn't specify time, return all values
        if self.request.data.get("grouping_unit") == "commit":
            max_num_commits = 1000
            commits = annotated_queryset.order_by(f"{coverage_ordering}timestamp")[
                :max_num_commits
            ]
            coverage = [
                {
                    "date": commits[index].timestamp,
                    "coverage": commits[index].coverage,
                    "coverage_change": commits[index].coverage
                    - commits[max(index - 1, 0)].coverage,
                    "commitid": commits[index].commitid,
                }
                for index in range(len(commits))
            ]

            complexity = [
                {
                    "date": commit.timestamp,
                    "complexity_ratio": round(commit.complexity_ratio * 100, 2),
                    "commitid": commit.commitid,
                }
                for commit in commits
                if commit.complexity_ratio is not None
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
                    "coverage_change": commits[index].coverage
                    - commits[max(index - 1, 0)].coverage,
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
                    "complexity_ratio": round(commit.complexity_ratio * 100, 2),
                    "commitid": commit.commitid,
                }
                for commit in complexity_grouped_queryset
                if commit.complexity_ratio is not None
            ]

        return Response(data={"coverage": coverage, "complexity": complexity})


class OrganizationChartHandler(APIView):
    """
    Returns array of datapoints retrieved by ChartQueryRunner.
    Response data format is:
    {
        "coverage": [
            {
                "date": "2019-06-01 00:00:00+00:00", <date for the time window>
                "coverage": <coverage calculated by taking (total_partials + total_hits) / total_lines>,
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

    # this method is deprecated and will be removed
    def post(self, request, *args, **kwargs):
        query_runner = ChartQueryRunner(
            user=request.user, request_params={**kwargs, **request.data}
        )
        return Response(data={"coverage": query_runner.run_query()})

    def get(self, request, *args, **kwargs):
        # Get request params as a dict. We take special care to preserve
        # the 'repositories' entry as a list, since the 'MultiValuedDict.dict'
        # method clobbers list values
        request_params_dict = request.query_params.dict()
        if "repositories" in request.query_params:
            request_params_dict.update(
                {"repositories": request.query_params.getlist("repositories")}
            )

        query_runner = ChartQueryRunner(
            user=request.user, request_params={**kwargs, **request_params_dict}
        )
        return Response(data={"coverage": query_runner.run_query()})
