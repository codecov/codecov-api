from datetime import timedelta
from functools import cached_property

from ariadne import ObjectType
from django.db import connections
from django.utils.timezone import now

from codecov.db import sync_to_async
from codecov_auth.models import Owner
from graphql_api.types.enums import GamificationMetric

leaderboard_data_bindable = ObjectType("LeaderboardData")
leaderboard_bindable = ObjectType("Leaderboard")


class LeaderboardData:
    def __init__(self, ownerid: int, value: float):
        self.ownerid = ownerid
        self.value = value

    @cached_property
    def author(self):
        return Owner.objects.filter(ownerid=self.ownerid).first()

    @cached_property
    def value(self):
        self.value


class Leaderboard:
    DEFAULT_RAW_QUERY = """
    SELECT
        owners.ownerid,
        leaderboard.metric
    FROM (
        SELECT
            p.author,
            {metric_compute} AS metric
        FROM owners o
        JOIN repos r ON o.ownerid = r.ownerid
        LEFT JOIN pulls p ON r.repoid = p.repoid
        WHERE
            p.author is not null
            AND o.ownerid = %s
            AND r.repoid = %s
            AND p.state = 'merged'
            AND p.updatestamp >= %s
        GROUP BY
            p.author
        {nested_extension}
    ) AS leaderboard
    LEFT JOIN owners ON leaderboard.author = owners.ownerid
    WHERE
        owners.username IS NOT null
        AND leaderboard.metric > 0
    ORDER BY leaderboard.metric DESC
    LIMIT 5;
    """

    METRIC_COMPUTES = {
        GamificationMetric.PATCH_COVERAGE_AVERAGE: {
            "metric_compute": "AVG((p.diff->5->>0)::FLOAT)",
            "nested_extension": "HAVING AVG((p.diff->5->>0)::FLOAT) IS NOT NULL",
        },
        GamificationMetric.CHANGE_COVERAGE_COUNT: {
            "metric_compute": "SUM(COALESCE((p.diff->2)::INT, 0))",
            "nested_extension": "",
        },
        GamificationMetric.PR_COUNT: {
            "metric_compute": "COUNT(p.author)",
            "nested_extension": "",
        },
    }

    def __init__(self, ownerid: int, repoid: int, metric: GamificationMetric):
        self.ownerid = ownerid
        self.repoid = repoid
        self.metric = metric

        self.metric_specific_query = Leaderboard.DEFAULT_RAW_QUERY.format(
            **Leaderboard.METRIC_COMPUTES[metric]
        )

    @cached_property
    def name(self):
        return self.metric

    @cached_property
    def ranking(self):
        start_date = now() - timedelta(days=30)
        with connections["default"].cursor() as cursor:
            cursor.execute(
                self.metric_specific_query, [self.ownerid, self.repoid, start_date]
            )
            return [LeaderboardData(*result) for result in cursor.fetchall()]


@leaderboard_data_bindable.field("author")
@sync_to_async
def resolve_author(leaderboard_data: LeaderboardData, info) -> Owner:
    return leaderboard_data.author


@leaderboard_data_bindable.field("value")
@sync_to_async
def resolve_vallue(leaderboard_data: LeaderboardData, info) -> float:
    return leaderboard_data.value


@leaderboard_bindable.field("name")
@sync_to_async
def resolve_name(leaderboard: Leaderboard, info) -> str:
    return leaderboard.name


@leaderboard_bindable.field("ranking")
@sync_to_async
def resolve_ranking(leaderboard: Leaderboard, info) -> str:
    return leaderboard.ranking
