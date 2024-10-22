import pytest

from utils.test_results import slow_test_threshold


@pytest.mark.parametrize(
    "total_tests, expected_threshold",
    [
        (0, 1),
        (1, 1),
        (10, 1),
        (100, 5),
        (1000, 50),
        (10000, 100),
        (1000000, 100),
        (20, 1),
        (50, 2),
        (200, 10),
        (2000, 100),
    ],
)
def test_slow_test_threshold(total_tests, expected_threshold):
    assert slow_test_threshold(total_tests) == expected_threshold
