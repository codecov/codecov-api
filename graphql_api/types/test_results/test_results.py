from datetime import datetime
from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo


class TestDict(TypedDict):
    name: str
    updated_at: datetime
    commits_where_fail: int
    failure_rate: float
    avg_duration: float
    last_duration: float
    flake_rate: float
    total_fail_count: int
    total_skip_count: int
    total_pass_count: int


test_result_bindable = ObjectType("TestResult")


@test_result_bindable.field("name")
def resolve_name(test: TestDict, _: GraphQLResolveInfo) -> str:
    return test.get("computed_name") or test["name"].replace("\x1f", " ")


@test_result_bindable.field("updatedAt")
def resolve_updated_at(test: TestDict, _: GraphQLResolveInfo) -> datetime:
    return test["updated_at"]


@test_result_bindable.field("commitsFailed")
def resolve_commits_failed(test: TestDict, _: GraphQLResolveInfo) -> int:
    return test["commits_where_fail"]


@test_result_bindable.field("failureRate")
def resolve_failure_rate(test: TestDict, _: GraphQLResolveInfo) -> float:
    return test["failure_rate"]


@test_result_bindable.field("flakeRate")
def resolve_flake_rate(test: TestDict, _: GraphQLResolveInfo) -> float:
    return test["flake_rate"]


@test_result_bindable.field("avgDuration")
def resolve_avg_duration(test: TestDict, _: GraphQLResolveInfo) -> float:
    return test["avg_duration"]


@test_result_bindable.field("lastDuration")
def resolve_last_duration(test: TestDict, _: GraphQLResolveInfo) -> float:
    return test["last_duration"]


@test_result_bindable.field("totalFailCount")
def resolve_total_fail_count(test: TestDict, _: GraphQLResolveInfo) -> int:
    return test["total_fail_count"]


@test_result_bindable.field("totalSkipCount")
def resolve_total_skip_count(test: TestDict, _: GraphQLResolveInfo) -> int:
    return test["total_skip_count"]


@test_result_bindable.field("totalPassCount")
def resolve_total_pass_count(test: TestDict, _: GraphQLResolveInfo) -> int:
    return test["total_pass_count"]
