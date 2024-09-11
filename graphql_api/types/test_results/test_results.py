from datetime import datetime

from ariadne import ObjectType

test_result_bindable = ObjectType("TestResult")


@test_result_bindable.field("name")
def resolve_name(test, info) -> str:
    return test["name"].replace("\x1f", " ")


@test_result_bindable.field("updatedAt")
def resolve_updated_at(test, info) -> datetime:
    return test["updated_at"]


@test_result_bindable.field("commitsFailed")
def resolve_commits_failed(test, info) -> int | None:
    return test["commits_where_fail"]


@test_result_bindable.field("failureRate")
def resolve_failure_rate(test, info) -> float | None:
    return test["failure_rate"]


@test_result_bindable.field("avgDuration")
def resolve_last_duration(test, info) -> float | None:
    return test["avg_duration"]
