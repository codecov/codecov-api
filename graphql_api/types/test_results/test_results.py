from ariadne import ObjectType

from reports.models import Test

test_result_bindable = ObjectType("TestResult")

@test_result_bindable.field("name")
def resolve_name(test: Test, info) -> str:
    return test.name

@test_result_bindable.field("updatedAt")
def resolve_updated_at(test: Test, info) -> str:
    return test.updated_at

@test_result_bindable.field("commitsFailed")
def resolve_commits_failed(test: Test, info) -> int or None:
    return test.commits_where_fail

@test_result_bindable.field("failureRate")
def resolve_failure_rate(test: Test, info) -> float or None:
    return test.failure_rate
