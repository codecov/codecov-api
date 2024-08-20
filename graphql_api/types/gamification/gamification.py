from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property

from ariadne import ObjectType
from django.db import connections
from django.utils.timezone import now

from codecov.db import sync_to_async
from codecov_auth.models import Owner
from graphql_api.types.enums import BadgeTier, GamificationMetric

leaderboard_data_bindable = ObjectType("LeaderboardData")
leaderboard_bindable = ObjectType("Leaderboard")
badge_bindable = ObjectType("Badge")


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


BADGE_METRIC_TIER_MAPPINGS = {
    GamificationMetric.PATCH_COVERAGE_AVERAGE: [
        (100, BadgeTier.GOLD),
        (90, BadgeTier.SILVER),
        (80, BadgeTier.BRONZE),
    ],
    GamificationMetric.CHANGE_COVERAGE_COUNT: [
        (200, BadgeTier.GOLD),
        (150, BadgeTier.SILVER),
        (100, BadgeTier.BRONZE),
    ],
    GamificationMetric.PR_COUNT: [
        (20, BadgeTier.GOLD),
        (15, BadgeTier.SILVER),
        (10, BadgeTier.BRONZE),
    ],
}


@dataclass
class Badge:
    name: GamificationMetric
    tier: BadgeTier


class BadgeCollection:
    DEFAULT_RAW_QUERY = """
    SELECT
        leaderboard.patch_coverage_average,
        leaderboard.change_coverage_count,
        leaderboard.pr_count
    FROM (
        SELECT
            p.author,
            AVG((p.diff->5->>0)::FLOAT) AS patch_coverage_average,
            SUM(COALESCE((p.diff->2)::INT, 0)) AS change_coverage_count,
            COUNT(p.author) AS pr_count
        FROM owners o
        JOIN repos r ON o.ownerid = r.ownerid
        LEFT JOIN pulls p ON r.repoid = p.repoid
        WHERE
            p.author = {author_ownerid}
            AND o.service = '{service}'
            AND o.username = %s
            AND r.name = %s
            AND p.state = 'merged'
            AND p.updatestamp >= %s
        GROUP BY
            p.author
    ) AS leaderboard
    LEFT JOIN owners ON leaderboard.author = owners.ownerid
    WHERE owners.username IS NOT null
    LIMIT 1
    """

    def __init__(self, service: str, author_ownerid: int):
        self.query = BadgeCollection.DEFAULT_RAW_QUERY.format(
            service=service,
            author_ownerid=author_ownerid,
        )

    def _badge_tier(self, metric: GamificationMetric, value: float) -> BadgeTier | None:
        for item in BADGE_METRIC_TIER_MAPPINGS[metric]:
            threshold, tier = item
            if value is None:
                return None
            elif value >= threshold:
                return tier
        return None

    def retrieve(self, organization_name: str, repository_name: str):
        start_date = now() - timedelta(days=30)
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query, [organization_name, repository_name, start_date])
            results = cursor.fetchall()
            if not results:
                return []

            patch_coverage_average, change_coverage_count, pr_count = results[0]

            print("actuals", patch_coverage_average, change_coverage_count, pr_count)

            badges = []
            patch_coverage_average_tier = self._badge_tier(
                GamificationMetric.PATCH_COVERAGE_AVERAGE, patch_coverage_average
            )
            if patch_coverage_average_tier:
                badges.append(
                    Badge(
                        GamificationMetric.PATCH_COVERAGE_AVERAGE,
                        patch_coverage_average_tier,
                    )
                )
            change_coverage_count_tier = self._badge_tier(
                GamificationMetric.CHANGE_COVERAGE_COUNT, change_coverage_count
            )
            if change_coverage_count_tier:
                badges.append(
                    Badge(
                        GamificationMetric.CHANGE_COVERAGE_COUNT,
                        change_coverage_count_tier,
                    )
                )
            pr_count_tier = self._badge_tier(GamificationMetric.PR_COUNT, pr_count)
            if pr_count_tier:
                badges.append(Badge(GamificationMetric.PR_COUNT, pr_count_tier))

            return badges


@leaderboard_data_bindable.field("author")
@sync_to_async
def resolve_leaderboard_data_author(leaderboard_data: LeaderboardData, info) -> Owner:
    return leaderboard_data.author


@leaderboard_data_bindable.field("value")
@sync_to_async
def resolve_leaderboard_data_value(leaderboard_data: LeaderboardData, info) -> float:
    return leaderboard_data.value


@leaderboard_bindable.field("name")
@sync_to_async
def resolve_leaderboard_name(leaderboard: Leaderboard, info) -> str:
    return leaderboard.name


@leaderboard_bindable.field("ranking")
@sync_to_async
def resolve_leaderboard_ranking(leaderboard: Leaderboard, info) -> str:
    return leaderboard.ranking


@badge_bindable.field("name")
@sync_to_async
def resolve_badge_name(badge: Badge, info) -> str:
    return badge.name


@badge_bindable.field("tier")
@sync_to_async
def resolve_badge_tier(badge: Badge, info) -> str:
    return badge.tier
