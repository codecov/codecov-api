from datetime import datetime

from utils.test_results import CursorValue, TestResultsRow, decode_cursor, encode_cursor


def test_cursor():
    row = TestResultsRow(
        test_id="test",
        name="test",
        updated_at=datetime.fromisoformat("2024-01-01T00:00:00Z"),
        commits_where_fail=1,
        failure_rate=0.5,
        avg_duration=100,
        last_duration=100,
        flake_rate=0.1,
        total_fail_count=1,
        total_flaky_fail_count=1,
        total_skip_count=1,
        total_pass_count=1,
    )
    cursor = encode_cursor(row, "updated_at")
    assert cursor == "MjAyNC0wMS0wMSAwMDowMDowMCswMDowMHx0ZXN0"
    decoded_cursor = decode_cursor(cursor)
    assert decoded_cursor == CursorValue(str(row.updated_at), "test")
