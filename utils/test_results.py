import datetime as dt

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Avg, Case, FloatField, Value, When
from shared.django_apps.reports.models import Test, TestInstance

thirty_days_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)


def aggregate_test_results(
    repoid: int, branch: str | None = None, history: dt.timedelta | None = None
):
    time_ago = (
        dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
        if history is not None
        else thirty_days_ago
    )

    pass_failure_error_test_instances = TestInstance.objects.filter(
        repoid=repoid,
        created_at__gt=time_ago,
        outcome__in=["pass", "failure", "error"],
    )

    failure_error_test_instances = pass_failure_error_test_instances.filter(
        outcome__in=["failure", "error"]
    )

    if branch is not None:
        pass_failure_error_test_instances = pass_failure_error_test_instances.filter(
            branch=branch
        )
        failure_error_test_instances = failure_error_test_instances.filter(
            branch=branch
        )

    failure_rates_queryset = pass_failure_error_test_instances.values(
        "test_id"
    ).annotate(
        failure_rate=Avg(
            Case(
                When(outcome="pass", then=Value(0.0)),
                When(outcome__in=["failure", "error"], then=Value(1.0)),
                output_field=FloatField(),
            )
        )
    )
    failure_rate_dict = {
        obj["test_id"]: obj["failure_rate"] for obj in failure_rates_queryset
    }

    commit_agg_queryset = failure_error_test_instances.values("test_id").annotate(
        commits=ArrayAgg("commitid", distinct=True)
    )
    commit_agg_dict = {obj["test_id"]: obj["commits"] for obj in commit_agg_queryset}

    average_duration_queryset = pass_failure_error_test_instances.values(
        "test_id"
    ).annotate(average_duration=Avg("duration_seconds"))

    average_duration_dict = {
        obj["test_id"]: obj["average_duration"] for obj in average_duration_queryset
    }

    tests = Test.objects.filter(repository_id=repoid).all()
    result = dict()
    for test in tests:
        result[test.id] = {
            "failure_rate": failure_rate_dict.get(test.id),
            "commits_where_fail": commit_agg_dict.get(test.id),
            "average_duration": average_duration_dict.get(test.id),
        }

    return result
