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


test_result_bindable = ObjectType("TestResult")


@test_result_bindable.field("name")
def resolve_name(test: TestDict, _: GraphQLResolveInfo) -> str:
    return test["name"].replace("\x1f", " ")


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
