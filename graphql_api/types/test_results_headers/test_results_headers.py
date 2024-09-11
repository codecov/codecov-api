from ariadne import ObjectType

test_results_headers_bindable = ObjectType("TestResultsHeaders")


@test_results_headers_bindable.field("totalRunTime")
def resolve_name(obj, _) -> float:
    return obj["total_run_time"]


@test_results_headers_bindable.field("slowestTestsRunTime")
def resolve_updated_at(obj, _) -> float:
    return obj["slowest_tests_duration"]


@test_results_headers_bindable.field("totalFails")
def resolve_commits_failed(obj, _) -> int:
    return obj["fails"]


@test_results_headers_bindable.field("totalSkips")
def resolve_failure_rate(obj, _) -> int:
    return obj["skips"]
