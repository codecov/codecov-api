from datetime import datetime

from utils.test_results import CursorValue, TestResultsRow, search_base_query


def row_factory(name: str, failure_rate: float):
    return TestResultsRow(
        test_id=name,
        name=name,
        failure_rate=failure_rate,
        flake_rate=0.0,
        updated_at=datetime.now(),
        avg_duration=0.0,
        total_fail_count=0,
        total_flaky_fail_count=0,
        total_pass_count=0,
        total_skip_count=0,
        commits_where_fail=0,
        last_duration=0.0,
    )


def test_search_base_query_cursor_val_none():
    rows = [row_factory(str(i), float(i) * 0.1) for i in range(10)]
    res = search_base_query(rows, "failure_rate", None)
    assert res == rows


def test_search_base_query_with_existing_cursor():
    rows = [row_factory(str(i), float(i) * 0.1) for i in range(10)]
    cursor = CursorValue(name="5", ordered_value="0.5")
    res = search_base_query(rows, "failure_rate", cursor)
    assert res == rows[6:]


def test_search_base_query_with_missing_cursor_high_name_low_failure_rate():
    # [(0, "0.0"), (1, "0.1"), (2, "0.2")]
    #            ^
    #          here's where the cursor is pointing at
    rows = [row_factory(str(i), float(i) * 0.1) for i in range(3)]
    cursor = CursorValue(name="111111", ordered_value="0.05")
    res = search_base_query(rows, "failure_rate", cursor)
    assert res == rows[1:]


def test_search_base_query_with_missing_cursor_low_name_high_failure_rate():
    # [(0, "0.0"), (1, "0.1"), (2, "0.2")]
    #                         ^
    #                        here's where the cursor is pointing at
    rows = [row_factory(str(i), float(i) * 0.1) for i in range(3)]
    cursor = CursorValue(name="0", ordered_value="0.15")
    res = search_base_query(rows, "failure_rate", cursor)
    assert res == rows[-1:]


def test_search_base_query_with_missing_cursor_low_name_high_failure_rate_desc():
    # [(2, "0.2"), (1, "0.1"), (0, "0.0")]
    #             ^
    #             here's where the cursor is pointing at
    rows = [row_factory(str(i), float(i) * 0.1) for i in range(2, -1, -1)]
    cursor = CursorValue(name="0", ordered_value="0.15")
    res = search_base_query(rows, "failure_rate", cursor, descending=True)
    assert res == rows[1:]
