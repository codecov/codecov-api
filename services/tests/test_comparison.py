import asyncio
import enum
import json
from collections import Counter
from unittest.mock import PropertyMock, patch

import minio
import pytest
from django.test import TestCase
from shared.reports.resources import ReportFile
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType

from codecov_auth.tests.factories import OwnerFactory
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from services.archive import SerializableReport
from services.comparison import (
    Comparison,
    ComparisonReport,
    CreateChangeSummaryVisitor,
    CreateLineComparisonVisitor,
    FileComparison,
    FileComparisonTraverseManager,
    ImpactedFile,
    LineComparison,
    MissingComparisonReport,
    PullRequestComparison,
    ImpactedFileParameter
)

# Pulled from core.tests.factories.CommitFactory files.
# Contents don't actually matter, it's just for providing a format
# compatible with what SerializableReport expects. Used in
# ComparisonTests.
file_data = [
    2,
    [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]


class MockOrderValue(object):
    def __init__(self, value):
        self.value = value

    def __getitem__(self, key):
        return getattr(self, key)


class OrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"


class LineNumberCollector:
    """
    A visitor for testing line traversal.
    """

    def __init__(self):
        self.line_numbers = []

    def __call__(self, base_ln, head_ln, value, is_diff):
        self.line_numbers.append((base_ln, head_ln))


class FileComparisonTraverseManagerTests(TestCase):
    def test_no_diff_results_in_no_line_number_adjustments(self):
        manager = FileComparisonTraverseManager(head_file_eof=3, base_file_eof=3)

        expected_result = [(1, 1), (2, 2)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_added_lines_adjusts_lines(self):
        # A line added at line 1 -- note header is string values, that's how
        # torngit returns it
        segments = [{"header": ["1", "1", "1", "2"], "lines": ["+"]}]

        manager = FileComparisonTraverseManager(
            head_file_eof=4, base_file_eof=3, segments=segments
        )

        expected_result = [(None, 1), (1, 2), (2, 3)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_removed_lines_adjusts_lines(self):
        # A line removed at line 1
        segments = [{"header": ["1", "1", "1", "2"], "lines": ["-"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=3, base_file_eof=4, segments=segments
        )

        expected_result = [(1, None), (2, 1), (3, 2)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_1_line_added_file_adjusts_lines(self):
        segments = [{"header": ["0", "0", "1", ""], "lines": ["+"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=2, base_file_eof=0, segments=segments
        )

        expected_result = [(None, 1)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_1_line_removed_file_adjusts_lines(self):
        segments = [{"header": ["1", "1", "0", ""], "lines": ["-"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=0, base_file_eof=2, segments=segments
        )

        expected_result = [(1, None)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_pop_line_returns_none_if_no_diff_or_src(self):
        manager = FileComparisonTraverseManager()
        assert manager.pop_line() == None

    def test_pop_line_pops_first_line_in_segment_if_traversing_that_segment(self):
        expected_line_value = "+this is a line!"
        segments = [
            {
                "header": [1, 2, 1, 3],
                "lines": [expected_line_value, "this is another line"],
            }
        ]
        manager = FileComparisonTraverseManager(segments=segments)
        assert manager.pop_line() == expected_line_value

    def test_pop_line_returns_line_at_head_ln_index_in_src_if_not_in_segment(self):
        expected_line_value = "a line from src!"
        manager = FileComparisonTraverseManager(
            head_file_eof=2, src=[expected_line_value]
        )
        assert manager.pop_line() == expected_line_value

    def test_traversing_diff_returns_true_if_head_ln_within_segment_at_position_0(self):
        manager = FileComparisonTraverseManager(
            segments=[{"header": ["1", "6", "12", "4"]}]
        )
        manager.head_ln = 14
        manager.base_ln = 1000
        assert manager.traversing_diff() is True

        manager.head_ln = 11
        assert manager.traversing_diff() is False

    def test_traversing_diff_handles_added_one_line_file_segment_header(self):
        segment = {"header": ["0", "0", "1", ""], "lines": ["+"]}
        manager = FileComparisonTraverseManager(segments=[segment])

        assert manager.traversing_diff() is True

    def test_traversing_diff_handles_removed_one_line_file_segment_header(self):
        segment = {"header": ["1", "1", "0", ""], "lines": ["-"]}
        manager = FileComparisonTraverseManager(segments=[segment])

        assert manager.traversing_diff() is True

    def test_traversing_diff_returns_true_if_base_ln_within_segment_at_position_0(self):
        manager = FileComparisonTraverseManager(
            segments=[{"header": ["4", "43", "4", "3"]}]
        )
        manager.head_ln = 7
        manager.base_ln = 44
        assert manager.traversing_diff() is True

    def test_traverse_finished_returns_false_even_both_line_counters_at_eof_and_traversing_diff(
        self,
    ):
        # This accounts for an edge case wherein you remove a multi-line expression
        # (which codecov counts as a single line, coverage-wise) at the
        # end of a file. The git-diff counts these as multiple lines, so
        # in order to not truncate the diff we need to continue popping
        # lines off the segment even of line counters are technically both
        # at EOF.
        manager = FileComparisonTraverseManager(
            head_file_eof=7,
            base_file_eof=43,
            segments=[{"header": ["4", "43", "4", "3"]}],
        )

        manager.base_ln = 45  # higher than eof, but still traversing_diff
        manager.head_ln = 7  # highest it can go in this segment

        assert manager.traverse_finished() is False

    def test_no_indexerror_if_basefile_longer_than_headfile_and_src_provided(self):
        manager = FileComparisonTraverseManager(
            head_file_eof=3,
            base_file_eof=4,
            src=["hey"] * 2,  # head file eof minus 1, which is the typical case
        )

        # No indexerror should occur
        manager.apply([lambda a, b, c, d: None])

    def test_can_traverse_diff_with_line_numbers_greater_than_file_eof(self):
        # This can happen when we have a file ending in a large multi-line
        # expression, and a diff is made somewhere within that expression,
        # but the start of the diff occurs after the start of the expression.
        # The previous implementation of "traverse_finished" would end the traverse
        # on account of not "traversing_diff", and having the line indices be
        # greater than the respective files' EOF. The fix for this bug is stronger
        # than that of the above comment and should handle both cases.
        segments = [
            {
                "header": ["3", "4", "3", "4"],
                "lines": ["-Pro Team (billed monthly)", "+Pro Team"],
            }
        ]
        manager = FileComparisonTraverseManager(
            head_file_eof=2, base_file_eof=2, segments=segments
        )

        visitor = LineNumberCollector()
        manager.apply([visitor])
        assert visitor.line_numbers == [(1, 1), (2, 2), (3, None), (None, 3)]


class CreateLineComparisonVisitorTests(TestCase):
    def setUp(self):
        self.head_file = ReportFile(
            "file1", lines=[[0, "", [], 0, 0], None, [0, "", [], 0, 0]]
        )
        self.base_file = ReportFile(
            "file1", lines=[None, [0, "", [], 0, 0], None, [0, "", [], 0, 0]]
        )

    def test_skips_if_line_value_is_none(self):
        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(0, 0, None, False)
        assert visitor.lines == []

    def test_appends_line_comparison_with_relevant_fields_if_line_value_not_none(self):
        base_ln = 2
        head_ln = 1
        base_line = self.base_file._lines[base_ln - 1]
        head_line = self.head_file._lines[head_ln - 1]
        value = "sup dood"
        is_diff = True

        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(base_ln, head_ln, value, is_diff)

        line = visitor.lines[0]
        assert line.head_ln == head_ln
        assert line.base_ln == base_ln
        assert line.head_line == head_line
        assert line.base_line == base_line
        assert line.value == value
        assert line.is_diff == is_diff

    def test_appends_line_comparison_with_no_base_line_if_no_base_file_or_line_not_in_base_file(
        self,
    ):
        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(100, 1, "", False)  # 100 is not a line in the base file
        assert visitor.lines[0].base_line is None

        visitor.base_file = None
        visitor(
            2, 1, "", False
        )  # all valid line numbers, but still expect none without base_file
        assert visitor.lines[1].base_line is None

    def test_appends_line_comparison_with_no_head_line_if_no_head_file_or_line_not_in_head_file(
        self,
    ):
        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(2, 100, "", False)
        assert visitor.lines[0].head_line is None

        visitor.head_file = None
        visitor(1, 2, "", False)
        assert visitor.lines[1].head_line is None


class CreateChangeSummaryVisitorTests(TestCase):
    def setUp(self):
        self.head_file = ReportFile("file1", lines=[[1, "", [], 0, 0]])
        self.base_file = ReportFile("file1", lines=[[0, "", [], 0, 0]])

    def test_changed_lines_in_diff_do_not_affect_change_summary(self):
        visitor = CreateChangeSummaryVisitor(self.base_file, self.head_file)
        visitor(1, 1, "+", False)
        assert visitor.summary == {}

        visitor(1, 1, "-", False)
        assert visitor.summary == {}

    def test_summary_with_one_less_miss_and_one_more_hit(self):
        visitor = CreateChangeSummaryVisitor(self.base_file, self.head_file)
        visitor(1, 1, "", True)
        assert visitor.summary == {"misses": -1, "hits": 1}

    def test_summary_with_one_less_hit_and_one_more_partial(self):
        self.base_file._lines[0][0] = 1
        self.head_file._lines[0][0] = "1/2"
        visitor = CreateChangeSummaryVisitor(self.base_file, self.head_file)
        visitor(1, 1, "", True)
        assert visitor.summary == {"hits": -1, "partials": 1}


class LineComparisonTests(TestCase):
    def test_number_shows_number_from_base_and_head(self):
        base_ln = 3
        head_ln = 4
        lc = LineComparison(
            [0, "", [], 0, 0], [0, "", [], 0, 0], base_ln, head_ln, "", False
        )
        assert lc.number == {"base": base_ln, "head": head_ln}

    def test_number_shows_none_for_base_if_added(self):
        head_ln = 4
        lc = LineComparison(None, [0, "", [], 0, 0], 0, head_ln, "+", False)
        assert lc.number == {"base": None, "head": head_ln}

    def test_number_shows_none_for_head_if_removed(self):
        base_ln = 3
        lc = LineComparison([0, "", [], 0, 0], None, base_ln, 0, "-", False)
        assert lc.number == {"base": base_ln, "head": None}

    def test_coverage_shows_coverage_for_base_and_head(self):
        base_cov, head_cov = 0, 1
        lc = LineComparison(
            [base_cov, "", [], 0, 0], [head_cov, "", [], 0, 0], 0, 0, "", False
        )
        assert lc.coverage == {"base": LineType.miss, "head": LineType.hit}

    def test_coverage_shows_none_for_base_if_added(self):
        head_cov = 1
        lc = LineComparison(None, [head_cov, "", [], 0, 0], 0, 0, "+", False)
        assert lc.coverage == {"base": None, "head": LineType.hit}

    def test_coverage_shows_none_for_head_if_removed(self):
        base_cov = 0
        lc = LineComparison([base_cov, "", [], 0, 0], None, 0, 0, "-", False)
        assert lc.coverage == {"base": LineType.miss, "head": None}

    def test_sessions_returns_sessions_hit_in_head(self):
        lc = LineComparison(
            None,
            [1, "", [[0, 1, 0, 0, 0], [1, 2, 0, 0, 0], [2, 1, 0, 0, 0]], 0, 0],
            0,
            0,
            "",
            False,
        )

        assert lc.sessions == 2

    def test_sessions_returns_none_if_no_coverage(self):
        lc = LineComparison(None, [0, "", [[0, 0, 0, 0, 0]], 0, 0], 0, 0, "", False)
        assert lc.sessions is None


class FileComparisonConstructorTests(TestCase):
    def test_constructor_no_keyError_if_diff_data_segements_is_missing(self):
        file_comp = FileComparison(
            head_file=ReportFile("file1"), base_file=ReportFile("file1"), diff_data={}
        )


class FileComparisonTests(TestCase):
    def setUp(self):
        self.file_comparison = FileComparison(
            head_file=ReportFile("file1"), base_file=ReportFile("file1")
        )

    def test_name_shows_name_for_base_and_head(self):
        assert self.file_comparison.name == {
            "base": self.file_comparison.base_file.name,
            "head": self.file_comparison.head_file.name,
        }

    def test_name_none_if_base_or_head_if_files_none(self):
        self.file_comparison.head_file = None
        assert self.file_comparison.name == {
            "base": self.file_comparison.base_file.name,
            "head": None,
        }

        self.file_comparison.base_file = None
        assert self.file_comparison.name == {"base": None, "head": None}

    def test_totals_shows_totals_for_base_and_head(self):
        assert self.file_comparison.totals == {
            "base": self.file_comparison.base_file.totals,
            "head": self.file_comparison.head_file.totals,
            "diff": None,
        }

    def test_totals_shows_totals_for_base_head_and_diff(self):
        diff_totals = ReportTotals.default_totals()
        self.file_comparison.diff_data = {
            "totals": diff_totals,
        }

        assert self.file_comparison.totals == {
            "base": self.file_comparison.base_file.totals,
            "head": self.file_comparison.head_file.totals,
            "diff": diff_totals,
        }

    def test_totals_base_is_none_if_missing_basefile(self):
        self.file_comparison.base_file = None
        assert self.file_comparison.totals == {
            "base": None,
            "head": self.file_comparison.head_file.totals,
            "diff": None,
        }

    def test_totals_head_is_none_if_missing_headfile(self):
        self.file_comparison.head_file = None
        assert self.file_comparison.totals == {
            "base": self.file_comparison.base_file.totals,
            "head": None,
            "diff": None,
        }

    def test_totals_includes_diff_totals_if_diff(self):
        totals = "these are the totals"
        self.file_comparison.diff_data = {"totals": totals}
        assert self.file_comparison.totals["head"].diff == totals

    def test_has_diff_returns_true_iff_diff_data_not_none(self):
        assert self.file_comparison.has_diff is False

        self.file_comparison.diff_data = {}
        assert self.file_comparison.has_diff is True

    def test_stats_returns_none_if_no_diff_data(self):
        assert self.file_comparison.has_diff is False
        assert self.file_comparison.stats is None

    def test_stats_returns_diff_stats_if_diff_data(self):
        expected_stats = "yep"
        self.file_comparison.diff_data = {"stats": expected_stats}
        assert self.file_comparison.stats == expected_stats

    def test_lines_returns_emptylist_if_no_diff_or_src(self):
        assert self.file_comparison.lines == []

    # essentially a smoke/integration test
    def test_lines(self):
        head_lines = [
            [1, "", [], 0, None],
            ["1/2", "", [], 0, None],
            [1, "", [], 0, None],
        ]
        base_lines = [[0, "", [], 0, None], [1, "", [], 0, None], [0, "", [], 0, None]]

        first_line_val = "unchanged line from src"
        second_line_val = "+this is an added line"
        third_line_val = "-this is a removed line"
        last_line_val = "this is the third line"

        segment = {
            "header": ["2", "2", "2", "2"],
            "lines": [second_line_val, third_line_val],
        }
        src = [first_line_val, "this is an added line", last_line_val]

        self.file_comparison.head_file._lines = head_lines
        self.file_comparison.base_file._lines = base_lines
        self.file_comparison.diff_data = {"segments": [segment]}
        self.file_comparison.src = src

        assert self.file_comparison.lines[0].value == first_line_val
        assert self.file_comparison.lines[0].number == {"base": 1, "head": 1}
        assert self.file_comparison.lines[0].coverage == {
            "base": LineType.miss,
            "head": LineType.hit,
        }

        assert self.file_comparison.lines[1].value == second_line_val
        assert self.file_comparison.lines[1].number == {"base": None, "head": 2}
        assert self.file_comparison.lines[1].coverage == {
            "base": None,
            "head": LineType.partial,
        }

        assert self.file_comparison.lines[2].value == third_line_val
        assert self.file_comparison.lines[2].number == {"base": 2, "head": None}
        assert self.file_comparison.lines[2].coverage == {
            "base": LineType.hit,
            "head": None,
        }

        assert self.file_comparison.lines[3].value == last_line_val
        assert self.file_comparison.lines[3].number == {"base": 3, "head": 3}
        assert self.file_comparison.lines[3].coverage == {
            "base": LineType.miss,
            "head": LineType.hit,
        }

    @patch("services.comparison.FileComparison.lines", new_callable=PropertyMock)
    def test_segments_diff_only(self, lines):
        lines.return_value = [
            LineComparison([1], [1], 1, 1, "first line", False),
            LineComparison(None, [1], None, 2, "+this is an added line", True),
            LineComparison([1], None, 2, None, "-this is a removed line", True),
            LineComparison([1], [1], 3, 3, "last line", False),
        ]

        segments = self.file_comparison.segments

        assert len(segments) == 1
        assert segments[0].lines == self.file_comparison.lines
        assert segments[0].header == (1, 3, 1, 3)
        assert segments[0].has_unintended_changes == False

    @patch("services.comparison.FileComparison.lines", new_callable=PropertyMock)
    def test_segments_changes_only(self, lines):
        lines.return_value = [
            LineComparison([1], [1], 1, 1, "first line", False),
            LineComparison([0], [1], 2, 2, "middle line", False),  # coverage added
            LineComparison([1], [1], 3, 3, "last line", False),
        ]

        segments = self.file_comparison.segments

        assert len(segments) == 1
        assert segments[0].lines == self.file_comparison.lines
        assert segments[0].header == (1, 3, 1, 3)
        assert segments[0].has_unintended_changes

    @patch("services.comparison.FileComparison.lines", new_callable=PropertyMock)
    def test_segments_no_changes_no_diff(self, lines):
        lines.return_value = [
            LineComparison([1], [1], 1, 1, "first line", False),
            LineComparison([1], [1], 2, 2, "middle line", False),
            LineComparison([1], [1], 3, 3, "last line", False),
        ]

        segments = self.file_comparison.segments
        assert len(segments) == 0

    def test_change_summary(self):
        head_lines = [
            [1, "", [], 0, None],
            ["3/4", "", [], 0, None],
            [1, "", [], 0, None],
        ]
        base_lines = [[0, "", [], 0, None], [1, "", [], 0, None], [0, "", [], 0, None]]

        first_line_val = "unchanged line from src"
        second_line_val = "+this is an added line"
        third_line_val = "-this is a removed line"
        last_line_val = "this is the third line"

        segment = {
            "header": ["2", "2", "2", "2"],
            "lines": [second_line_val, third_line_val],
        }
        src = [first_line_val, "this is an added line", last_line_val]

        self.file_comparison.head_file._lines = head_lines
        self.file_comparison.base_file._lines = base_lines
        self.file_comparison.diff_data = {"segments": [segment]}
        self.file_comparison.src = src

        assert self.file_comparison.change_summary == {"hits": 2, "misses": -2}

    @patch(
        "services.comparison.FileComparison.change_summary", new_callable=PropertyMock
    )
    def test_has_changes(self, change_summary_mock):
        change_summary_mock.return_value = Counter()
        assert self.file_comparison.has_changes == False

        change_summary_mock.return_value = Counter({"hits": 0, "misses": 0})
        assert self.file_comparison.has_changes == False

        change_summary_mock.return_value = Counter({"hits": 1, "misses": -1})
        assert self.file_comparison.has_changes == True

    @patch("services.comparison.FileComparisonTraverseManager.apply")
    def test_does_not_calculate_changes_if_no_diff_and_should_search_for_changes_is_False(
        self, mocked_apply_traverse
    ):
        self.file_comparison.should_search_for_changes = False
        self.file_comparison._calculated_changes_and_lines
        mocked_apply_traverse.assert_not_called()

    @patch("services.comparison.FileComparisonTraverseManager.apply")
    def test_calculates_changes_if_no_diff_and_should_search_for_changes_is_None(
        self, mocked_apply_traverse
    ):
        self.file_comparison.should_search_for_changes = None
        self.file_comparison._calculated_changes_and_lines
        mocked_apply_traverse.assert_called_once()

    @patch("services.comparison.FileComparisonTraverseManager.apply")
    def test_calculates_changes_should_search_for_changes_is_True(
        self, mocked_apply_traverse
    ):
        self.file_comparison.should_search_for_changes = True
        self.file_comparison._calculated_changes_and_lines
        mocked_apply_traverse.assert_called_once()

    @patch("services.comparison.FileComparisonTraverseManager.apply")
    def test_calculates_changes_if_traversing_src(self, mocked_apply_traverse):
        self.file_comparison.should_search_for_changes = False
        self.file_comparison.src = ["a truthy list"]
        self.file_comparison._calculated_changes_and_lines
        mocked_apply_traverse.assert_called_once()


@patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
@patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
@patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
class ComparisonTests(TestCase):
    def setUp(self):
        owner = OwnerFactory()
        base, head = CommitFactory(author=owner), CommitFactory(author=owner)
        self.comparison = Comparison(user=owner, base_commit=base, head_commit=head)

    def test_files_gets_file_comparison_for_each_file_in_head_report(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        head_report_files = {"file1": file_data, "file2": file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)
        base_report_mock.return_value = SerializableReport(files={})
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        assert sum(1 for x in self.comparison.files) == 2
        for fc in self.comparison.files:
            assert isinstance(fc, FileComparison)
            assert fc.head_file.name in head_report_files
            assert fc.base_file is None

    def test_get_file_comparison_adds_in_file_from_base_report_if_exists(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        files = {"both.py": file_data}
        base_report_mock.return_value = SerializableReport(files=files)
        head_report_mock.return_value = SerializableReport(files=files)

        fc = self.comparison.get_file_comparison("both.py")
        assert fc.head_file.name == "both.py"
        assert fc.base_file.name == "both.py"

    def test_get_file_comparison_accounts_for_renamed_files(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        file_name = "myfile.py"
        previous_name = "previous.py"

        base_report_files = {previous_name: file_data}
        base_report_mock.return_value = SerializableReport(files=base_report_files)

        head_report_files = {file_name: file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {
            "diff": {"files": {file_name: {"before": previous_name, "segments": []}}},
            "commits": [],
        }

        fc = self.comparison.get_file_comparison(file_name)
        assert fc.head_file.name == file_name
        assert fc.base_file.name == previous_name

    def test_get_file_comparison_includes_diff_data_if_exists(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        file_name = "f"
        diff_data = {
            "segments": [{"header": ["4", "6", "7", "3"], "lines": []}],
            "stats": {"added": 3, "removed": 2},
        }

        base_report_mock.return_value = SerializableReport(files={})

        head_report_files = {file_name: file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {"diff": {"files": {file_name: diff_data}}}

        fc = self.comparison.get_file_comparison(file_name)
        assert fc.diff_data == diff_data

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_get_file_comparison_includes_src_if_with_src_is_true(
        self,
        mocked_comparison_adapter,
        base_report_mock,
        head_report_mock,
        git_comparison_mock,
    ):
        from api.internal.tests.views.test_compare_viewset import (
            MockedComparisonAdapter,
        )

        src = b"two\nlines"
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        mocked_comparison_adapter.return_value = MockedComparisonAdapter(
            {"diff": {"files": {}}}, test_lines=src
        )

        file_name = "f"

        base_report_mock.return_value = SerializableReport(files={})
        head_report_files = {file_name: file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        fc = self.comparison.get_file_comparison(file_name, with_src=True)
        assert fc.src == ["two", "lines"]

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_get_file_comparison_can_parse_string_src(
        self,
        mocked_comparison_adapter,
        base_report_mock,
        head_report_mock,
        git_comparison_mock,
    ):
        from api.internal.tests.views.test_compare_viewset import (
            MockedComparisonAdapter,
        )

        src = "two\nlines"
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        mocked_comparison_adapter.return_value = MockedComparisonAdapter(
            {"diff": {"files": {}}}, test_lines=src
        )

        file_name = "f"

        base_report_mock.return_value = SerializableReport(files={})
        head_report_files = {file_name: file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        fc = self.comparison.get_file_comparison(file_name, with_src=True)
        assert fc.src == ["two", "lines"]

    def test_get_file_comparison_with_no_base_report_doesnt_crash(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        files = {"both.py": file_data}
        base_report_mock.return_value = None
        head_report_mock.return_value = SerializableReport(files=files)

        fc = self.comparison.get_file_comparison("both.py")
        assert fc.head_file.name == "both.py"

    @pytest.mark.xfail  # TODO(pierce): investigate this feature
    def test_files_adds_deleted_files_that_were_tracked_in_base_report(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        deleted_file_name = "deleted.py"
        base_report_files = {deleted_file_name: file_data}
        base_report_mock.return_value = SerializableReport(files=base_report_files)

        head_report_files = {}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {
            "diff": {"files": {deleted_file_name: {"type": "deleted"}}},
            "commits": [],
        }

        assert self.comparison.files[0].base_file.name == deleted_file_name
        assert self.comparison.files[0].head_file is None
        assert self.comparison.files[0].diff_data == {"type": "deleted"}

    def test_totals_returns_head_totals_if_exists(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.return_value = SerializableReport()

        assert self.comparison.totals["head"] == head_report_mock.return_value.totals
        assert self.comparison.totals["base"] is None

    def test_totals_returns_base_totals_if_exists(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        head_report_mock.return_value = None
        base_report_mock.return_value = SerializableReport()

        assert self.comparison.totals["base"] == base_report_mock.return_value.totals
        assert self.comparison.totals["head"] is None

    def test_totals_returns_diff_totals_if_exists(
        self, base_report_mock, head_report_mock, git_comparison_mock
    ):
        head_report = SerializableReport()
        head_report_mock.return_value = head_report
        base_report_mock.return_value = None

        diff_totals = ReportTotals.default_totals()
        git_comparison_mock.return_value = {"diff": {"totals": diff_totals}}

        assert self.comparison.totals["base"] is None
        assert self.comparison.totals["head"] == head_report.totals
        assert self.comparison.totals["diff"] is diff_totals

    def test_head_and_base_reports_have_cff_sessions(
        self, base_report_mock, head_report_mock, _
    ):
        # Only relevant files keys to the session object
        head_report_sessions = {"0": {"st": "carriedforward"}}
        head_report = SerializableReport(sessions=head_report_sessions)
        head_report_mock.return_value = head_report
        base_report_sessions = {"0": {"st": "carriedforward"}}
        base_report = SerializableReport(sessions=base_report_sessions)
        base_report_mock.return_value = base_report

        fc = self.comparison.has_different_number_of_head_and_base_sessions
        assert fc == False

    def test_head_and_base_reports_have_different_number_of_reports(
        self, base_report_mock, head_report_mock, _
    ):
        # Only relevant files keys to the session object
        head_report_sessions = {"0": {"st": "uploaded"}, "1": {"st": "uploaded"}}
        head_report = SerializableReport(sessions=head_report_sessions)
        head_report_mock.return_value = head_report
        base_report_sessions = {"0": {"st": "uploaded"}}
        base_report = SerializableReport(sessions=base_report_sessions)
        base_report_mock.return_value = base_report

        fc = self.comparison.has_different_number_of_head_and_base_sessions
        assert fc == True

    def test_head_and_base_reports_have_same_number_of_reports(
        self, base_report_mock, head_report_mock, _
    ):
        # Only relevant files keys to the session object
        head_report_sessions = {"0": {"st": "uploaded"}}
        head_report = SerializableReport(sessions=head_report_sessions)
        head_report_mock.return_value = head_report
        base_report_sessions = {"0": {"st": "uploaded"}}
        base_report = SerializableReport(sessions=base_report_sessions)
        base_report_mock.return_value = base_report

        fc = self.comparison.has_different_number_of_head_and_base_sessions
        assert fc == False


class PullRequestComparisonTests(TestCase):
    def setUp(self):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head, compared_to = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )

        self.pull = PullFactory(
            repository=repo,
            base=base.commitid,
            head=head.commitid,
            compared_to=compared_to.commitid,
        )
        self.comparison = PullRequestComparison(user=owner, pull=self.pull)

    def test_files_with_changes_hash_key(self):
        assert self.comparison._files_with_changes_hash_key == "/".join(
            (
                "compare-changed-files",
                self.pull.repository.author.service,
                self.pull.repository.author.username,
                self.pull.repository.name,
                str(self.pull.pullid),
            )
        )

    @patch("redis.Redis.get")
    def test_files_with_changes_retrieves_from_redis(self, mocked_get):
        filename = "something.py"
        mocked_get.return_value = json.dumps([filename])
        assert self.comparison._files_with_changes == [filename]

    @patch("redis.Redis.get")
    def test_files_with_changes_returns_none_if_no_files_with_changes(self, mocked_get):
        mocked_get.return_value = None
        assert self.comparison._files_with_changes == None

    @patch("redis.Redis.get")
    def test_files_with_changes_doesnt_crash_if_redis_connection_problem(
        self, mocked_get
    ):
        def raise_oserror(*args, **kwargs):
            raise OSError

        mocked_get.side_effect = raise_oserror
        self.comparison._files_with_changes

    @patch("redis.Redis.set")
    def test_set_files_with_changes_in_cache_stores_in_redis(self, mocked_set):
        files_with_changes = ["file1", "file2"]
        self.comparison._set_files_with_changes_in_cache(files_with_changes)
        mocked_set.assert_called_once_with(
            self.comparison._files_with_changes_hash_key,
            json.dumps(files_with_changes),
            ex=86400,  # 1 day in seconds
        )

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
    @patch("redis.Redis.set")
    @patch("redis.Redis.get")
    @patch(
        "services.comparison.FileComparison.change_summary", new_callable=PropertyMock
    )
    def test_files_populates_files_with_changes_in_redis(
        self,
        mocked_change_summary,
        mocked_get,
        mocked_set,
        base_report_mock,
        head_report_mock,
        git_comparison_mock,
    ):
        mocked_get.return_value = None
        mocked_change_summary.return_value = {"hits": 1, "misses": -1}
        head_report_files = {"file1": file_data, "file2": file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)
        base_report_mock.return_value = SerializableReport(files={})
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        list(self.comparison.files)

        mocked_set.assert_called_once_with(
            self.comparison._files_with_changes_hash_key,
            json.dumps(["file1", "file2"]),
            ex=86400,  # 1 day in seconds
        )

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
    @patch(
        "services.comparison.PullRequestComparison._files_with_changes",
        new_callable=PropertyMock,
    )
    def test_get_file_comparison_sets_should_search_for_changes_correctly(
        self,
        files_with_changes_mock,
        base_report_mock,
        head_report_mock,
        git_comparison_mock,
    ):
        head_report_files = {"file1": file_data, "file2": file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)
        base_report_mock.return_value = SerializableReport(files={})
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        with self.subTest("it's None when nothing found in cache"):
            files_with_changes_mock.return_value = None
            fc = self.comparison.get_file_comparison("file1")
            assert fc.should_search_for_changes is None

        with self.subTest("it's True when file found in cached list"):
            files_with_changes_mock.return_value = ["file1"]
            fc = self.comparison.get_file_comparison("file1")
            assert fc.should_search_for_changes is True

        with self.subTest("it's False when file not found in list"):
            files_with_changes_mock.return_value = ["file2"]
            fc = self.comparison.get_file_comparison("file1")
            assert fc.should_search_for_changes is False

    @patch("services.comparison.get_config")
    def test_is_pseudo_comparison(self, get_config_mock):
        owner = OwnerFactory()
        repository = RepositoryFactory(author=owner)
        pull = PullFactory(
            pullid=44,
            repository=repository,
            compared_to=CommitFactory(repository=repository).commitid,
            head=CommitFactory(repository=repository).commitid,
            base=CommitFactory(repository=repository).commitid,
        )

        with self.subTest("returns the result in the repo yaml if exists"):
            repository.yaml = {"codecov": {"allow_pseudo_compare": True}}
            repository.save()
            comparison = PullRequestComparison(owner, pull)
            assert comparison.is_pseudo_comparison is True

            repository.yaml = {"codecov": {"allow_pseudo_compare": False}}
            repository.save()
            comparison = PullRequestComparison(owner, pull)
            assert comparison.is_pseudo_comparison is False

        with self.subTest(
            "returns the result in app settings if repo yaml doesn't exist"
        ):
            repository.yaml = None
            repository.save()
            get_config_mock.return_value = True
            comparison = PullRequestComparison(owner, pull)
            assert comparison.is_pseudo_comparison is True

        with self.subTest(
            "returns the result in app settings if repo yaml doesn't exist"
        ):
            repository.yaml = None
            repository.save()
            get_config_mock.return_value = False
            comparison = PullRequestComparison(owner, pull)
            assert comparison.is_pseudo_comparison is False

        with self.subTest("depends on the truthiness of the 'compared_to' commit"):
            repository.yaml = {"codecov": {"allow_pseudo_compare": True}}
            repository.save()
            pull.compared_to = None
            pull.save()
            comparison = PullRequestComparison(owner, pull)
            assert comparison.is_pseudo_comparison is False

    @patch("services.comparison.get_config")
    def test_allow_coverage_offsets(self, get_config_mock):
        owner = OwnerFactory()
        repository = RepositoryFactory(author=owner)
        pull = PullFactory(
            pullid=44,
            repository=repository,
            compared_to=CommitFactory(repository=repository).commitid,
            head=CommitFactory(repository=repository).commitid,
            base=CommitFactory(repository=repository).commitid,
        )

        with self.subTest("returns result in repo yaml if exists"):
            repository.yaml = {"codecov": {"allow_coverage_offsets": True}}
            repository.save()
            comparison = PullRequestComparison(owner, pull)
            assert comparison.allow_coverage_offsets is True

            repository.yaml = {"codecov": {"allow_coverage_offsets": False}}
            repository.save()
            comparison = PullRequestComparison(owner, pull)
            assert comparison.allow_coverage_offsets is False

        repository.yaml = None
        repository.save()

        with self.subTest("returns app settings value if exists, True if not"):
            get_config_mock.return_value = True
            comparison = PullRequestComparison(owner, pull)
            comparison.allow_coverage_offsets is True

            get_config_mock.return_value = False
            comparison = PullRequestComparison(owner, pull)
            comparison.allow_coverage_offsets is False

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_pseudo_diff_returns_diff_between_base_and_compared_to(
        self, get_adapter_mock
    ):
        expected_diff = "expected_diff"

        class PseudoCompareAdapter:
            async def get_compare(self, base, head):
                self.base, self.head = base, head
                return {"diff": expected_diff}

        get_compare_adapter = PseudoCompareAdapter()
        get_adapter_mock.return_value = get_compare_adapter

        assert self.comparison.pseudo_diff == expected_diff
        assert (
            get_compare_adapter.base == self.pull.compared_to
            and get_compare_adapter.head == self.pull.base
        )

    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    @patch(
        "services.comparison.PullRequestComparison.pseudo_diff",
        new_callable=PropertyMock,
    )
    @patch("shared.reports.resources.Report.does_diff_adjust_tracked_lines")
    @patch(
        "services.comparison.PullRequestComparison.is_pseudo_comparison",
        new_callable=PropertyMock,
    )
    def test_pseudo_diff_adjusts_tracked_lines(
        self,
        is_pseudo_comparison_mock,
        does_diff_adjust_mock,
        pseudo_diff_mock,
        git_comparison_mock,
        base_report_mock,
        head_report_mock,
    ):
        owner = OwnerFactory()
        repository = RepositoryFactory(author=owner)
        pull = PullFactory(
            pullid=44,
            repository=repository,
            compared_to=CommitFactory(repository=repository).commitid,
            head=CommitFactory(repository=repository).commitid,
            base=CommitFactory(repository=repository).commitid,
        )

        with self.subTest(
            "returns True if reports exist and there is a diff that adjusts tracked lines"
        ):
            is_pseudo_comparison_mock.return_value = True
            head_report_files = {"file1": file_data, "file2": file_data}
            head_report_mock.return_value = SerializableReport(files=head_report_files)
            base_report_mock.return_value = SerializableReport(files={})
            git_comparison_mock.return_value = {"diff": {"files": {}}}
            pseudo_diff_mock.return_value = {"files": {"file1": {}}}
            does_diff_adjust_mock.return_value = True
            comparison = PullRequestComparison(owner, pull)
            assert comparison.pseudo_diff_adjusts_tracked_lines is True

        with self.subTest("returns False if reports don't exist"):
            head_report_mock.return_value = None
            comparison = PullRequestComparison(owner, pull)
            assert self.comparison.pseudo_diff_adjusts_tracked_lines is False

            head_report_mock.return_value = SerializableReport(files=head_report_files)
            base_report_mock.return_value = None
            comparison = PullRequestComparison(owner, pull)
            assert self.comparison.pseudo_diff_adjusts_tracked_lines is False

        with self.subTest("returns False if compared to is same as base"):
            self.comparison.pull.compared_to = self.comparison.pull.base
            self.comparison.pull.save()
            comparison = PullRequestComparison(owner, pull)
            assert self.comparison.pseudo_diff_adjusts_tracked_lines is False

        with self.subTest("returns False for non-pseudo comparisons"):
            is_pseudo_comparison_mock.return_value = True
            comparison = PullRequestComparison(owner, pull)
            assert self.comparison.pseudo_diff_adjusts_tracked_lines is False

    @patch(
        "services.comparison.PullRequestComparison.pseudo_diff",
        new_callable=PropertyMock,
    )
    @patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
    @patch("shared.reports.resources.Report.shift_lines_by_diff")
    def test_update_base_report_with_pseudo_diff(
        self, shift_lines_by_diff_mock, base_report_mock, pseudo_diff_mock
    ):
        pseudo_diff_mock.return_value = {"files": {}}
        base_report_files = {"file1": file_data, "file2": file_data}
        base_report_mock.return_value = SerializableReport(files=base_report_files)
        self.comparison.update_base_report_with_pseudo_diff()
        shift_lines_by_diff_mock.assert_called_once_with({"files": {}}, forward=True)


@patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
@patch("services.archive.ReportService.build_report_from_commit")
class ComparisonHeadReportTests(TestCase):
    def setUp(self):
        owner = OwnerFactory()
        base, head = CommitFactory(author=owner), CommitFactory(author=owner)
        self.comparison = Comparison(base, head, owner)

    @patch("services.archive.SerializableReport.apply_diff")
    def test_head_report_calls_apply_diff(
        self, apply_diff_mock, build_report_from_commit_mock, git_comparison_mock
    ):
        build_report_from_commit_mock.return_value = SerializableReport(
            files={"f": file_data}
        )
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        # should be called when invoking this property
        self.comparison.head_report

        apply_diff_mock.assert_called_once_with(
            git_comparison_mock.return_value["diff"]
        )

    def test_head_report_and_base_report_translates_nosuchkey_into_missingcomparisonreport(
        self, build_report_from_commit_mock, git_comparison_mock
    ):
        build_report_from_commit_mock.side_effect = minio.error.NoSuchKey()
        with self.assertRaises(MissingComparisonReport):
            self.comparison.head_report

        with self.assertRaises(MissingComparisonReport):
            self.comparison.base_report


@patch("services.repo_providers.RepoProviderService.get_adapter")
class ComparisonHasUnmergedBaseCommitsTests(TestCase):
    class MockFetchDiffCoro:
        def __init__(self, commits):
            self.commits = commits

        async def get_compare(self, base, head):
            return {"commits": self.commits}

    def setUp(self):
        owner = OwnerFactory()
        base, head = CommitFactory(author=owner), CommitFactory(author=owner)
        self.comparison = Comparison(user=owner, base_commit=base, head_commit=head)
        asyncio.set_event_loop(asyncio.new_event_loop())

    def test_returns_true_if_reverse_comparison_has_commits(self, get_adapter_mock):
        commits = ["a", "b"]
        get_adapter_mock.return_value = (
            ComparisonHasUnmergedBaseCommitsTests.MockFetchDiffCoro(commits)
        )
        assert self.comparison.has_unmerged_base_commits is True

    def test_returns_false_if_reverse_comparison_has_one_commit_or_less(
        self, get_adapter_mock
    ):
        commits = ["a"]
        get_adapter_mock.return_value = (
            ComparisonHasUnmergedBaseCommitsTests.MockFetchDiffCoro(commits)
        )
        assert self.comparison.has_unmerged_base_commits is False


class SegmentTests(TestCase):
    def _report_lines(self, hits):
        return [
            # from shared.reports.types.ReportLine
            # values are [coverage, type, sessions, messages, complexity]
            [hit, "", [], 0, None]
            for hit in hits
        ]

    def _src(self, n):
        return [f"line{i+1}" for i in range(n)]

    def setUp(self):
        self.file_comparison = FileComparison(
            base_file=ReportFile("file1"), head_file=ReportFile("file1")
        )

    def test_single_segment(self):
        self.file_comparison.src = self._src(12)
        self.file_comparison.head_file._lines = self._report_lines(
            [1 for _ in range(12)]
        )
        self.file_comparison.base_file._lines = self._report_lines(
            [
                1,
                1,  # first line of segment
                1,
                1,
                0,  # coverage changed
                0,  # coverage changed
                1,
                0,  # coverage changed
                1,
                1,
                1,  # last line of segment
                1,
            ]
        )

        segments = self.file_comparison.segments
        assert len(segments) == 1

        segment_lines = segments[0].lines
        assert segment_lines[0].value == "line2"
        assert segment_lines[-1].value == "line11"
        assert len(segment_lines) == 10

    def test_multiple_segments(self):
        self.file_comparison.src = self._src(25)
        self.file_comparison.head_file._lines = self._report_lines(
            [1 for _ in range(25)]
        )
        self.file_comparison.base_file._lines = self._report_lines(
            [
                1,
                1,  # first line of segment 1
                1,
                1,
                0,  # coverage changed
                0,  # coverage changed
                1,
                0,  # coverage changed
                1,
                1,
                1,  # last line of segment 1
                1,
                1,
                1,
                1,
                1,  # first line of segment 2
                1,
                1,
                0,  # coverage changed
                1,
                1,
                1,  # last line of segment 2
                1,
                1,
                1,
            ]
        )

        segments = self.file_comparison.segments
        assert len(segments) == 2

        assert segments[0].lines[0].value == "line2"
        assert segments[0].lines[-1].value == "line11"
        assert len(segments[0].lines) == 10
        assert segments[0].header == (2, 10, 2, 10)
        assert segments[0].has_unintended_changes

        assert segments[1].lines[0].value == "line16"
        assert segments[1].lines[-1].value == "line22"
        assert len(segments[1].lines) == 7
        assert segments[1].header == (16, 7, 16, 7)
        assert segments[1].has_unintended_changes

    @patch("services.comparison.FileComparison.lines", new_callable=PropertyMock)
    def test_header_new_file(self, lines):
        lines.return_value = [
            LineComparison(None, [1], None, 1, "+line1", True),
            LineComparison(None, [1], None, 2, "+line2", True),
            LineComparison(None, [1], None, 3, "+line3", True),
        ]

        file_comparison = FileComparison(base_file=None, head_file=ReportFile("file1"))

        segments = file_comparison.segments
        assert len(segments) == 1
        assert segments[0].header == (0, 0, 1, 3)

    @patch("services.comparison.FileComparison.lines", new_callable=PropertyMock)
    def test_header_deleted_file(self, lines):
        lines.return_value = [
            LineComparison([1], None, 1, None, "-line1", True),
            LineComparison([1], None, 2, None, "-line2", True),
            LineComparison([1], None, 3, None, "-line3", True),
        ]

        file_comparison = FileComparison(base_file=ReportFile("file1"), head_file=None)

        segments = file_comparison.segments
        assert len(segments) == 1
        assert segments[0].header == (1, 3, 0, 0)


mock_data_from_archive = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 2,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "m"]]]
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": []
    }]
}
"""


class ComparisonReportTest(TestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            report_storage_path="v4/test.json",
        )
        self.comparison_without_storage = CommitComparisonFactory()
        self.comparison_report = ComparisonReport(self.comparison)
        self.comparison_report_without_storage = ComparisonReport(
            self.comparison_without_storage
        )

    def test_empty_impacted_files(self):
        impacted_files = self.comparison_report_without_storage.impacted_files
        assert impacted_files == []

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_error_when_failing_to_get_file_from_storage(
        self, mock_read_file
    ):
        mock_read_file.side_effect = Exception()
        impacted_files = self.comparison_report.impacted_files
        assert impacted_files == []

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_without_filters(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {}
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file(self, read_file):
        read_file.return_value = mock_data_from_archive
        impacted_file = self.comparison_report.impacted_file("fileB")
        assert impacted_file == ImpactedFile(
            file_name="fileB",
            base_name="fileB",
            head_name="fileB",
            base_coverage=ReportTotals(
                files=0,
                lines=0,
                hits=5,
                misses=6,
                partials=1,
                coverage=41.666666666666664,
                branches=2,
                methods=4,
                messages=0,
                sessions=0,
                complexity=0,
                complexity_total=0,
                diff=0,
            ),
            head_coverage=ReportTotals(
                files=0,
                lines=0,
                hits=12,
                misses=1,
                partials=1,
                coverage=85.71428571428571,
                branches=3,
                methods=5,
                messages=0,
                sessions=0,
                complexity=0,
                complexity_total=0,
                diff=0,
            ),
            patch_coverage=ReportTotals(
                files=0,
                lines=0,
                hits=5,
                misses=1,
                partials=1,
                coverage=71.42857142857143,
                branches=0,
                methods=0,
                messages=0,
                sessions=0,
                complexity=0,
                complexity_total=0,
                diff=0,
            ),
            change_coverage=44.047619047619044,
            misses_in_comparison=1,
        )

    def test_impacted_file_sort_function(self):
        impacted_files = [
            ImpactedFile(
                file_name="words.js",
                base_name="flag2/words.js",
                head_name="flag2/words.js",
                base_coverage=None,
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=None,
                change_coverage=None,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="mafs.js",
                base_name="flag1/mafs.js",
                head_name="flag1/mafs.js",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=7,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=58.333333333333336,
                misses_in_comparison=5,
            ),
            ImpactedFile(
                file_name="mafs.js",
                base_name="flag1/mafs.js",
                head_name="flag1/mafs.js",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=100,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=7,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=0,
                misses_in_comparison=32,
            ),
        ]
        parameter = ImpactedFileParameter.CHANGE_COVERAGE
        direction = OrderingDirection.DESC
        sorted_files = self.comparison_report.sort_impacted_files(
            impacted_files, parameter, direction
        )
        assert sorted_files == [
            ImpactedFile(
                file_name="mafs.js",
                base_name="flag1/mafs.js",
                head_name="flag1/mafs.js",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=7,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=58.333333333333336,
                misses_in_comparison=5,
            ),
            ImpactedFile(
                file_name="mafs.js",
                base_name="flag1/mafs.js",
                head_name="flag1/mafs.js",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=100,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=7,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=0,
                misses_in_comparison=32,
            ),
            ImpactedFile(
                file_name="words.js",
                base_name="flag2/words.js",
                head_name="flag2/words.js",
                base_coverage=None,
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=None,
                change_coverage=None,
                misses_in_comparison=3,
            ),
        ]

    def test_impacted_file_sort_function_error(self):
        impacted_files = [
            ImpactedFile(
                file_name="mafs.js",
                base_name="flag1/mafs.js",
                head_name="flag1/mafs.js",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=100,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=7,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=0,
                misses_in_comparison=3,
            ),
        ]
        parameter = "something else"
        direction = OrderingDirection.DESC
        with self.assertRaises(ValueError) as ctx:
            self.comparison_report.sort_impacted_files(
                impacted_files, parameter, direction
            )
        self.assertEqual(
            "invalid impacted file parameter: something else", str(ctx.exception)
        )

    def test_impacted_file_deserialize_file(self):
        file = {
            "base_name": "flag2/words.js",
            "head_name": "flag2/words.js",
            "file_was_added_by_diff": False,
            "file_was_removed_by_diff": False,
            "base_coverage": None,
            "head_coverage": {
                "hits": 12,
                "misses": 1,
                "partials": 1,
                "branches": 3,
                "sessions": 0,
                "complexity": 0,
                "complexity_total": 0,
                "methods": 5,
            },
            "removed_diff_coverage": None,
            "added_diff_coverage": [],
            "unexpected_line_changes": [
                [[1, None], [1, "h"]],
                [[2, None], [2, "h"]],
                [[5, None], [5, "h"]],
                [[6, None], [6, "h"]],
                [[9, None], [9, "m"]],
                [[10, None], [10, "p"]],
                [[14, None], [13, "h"]],
                [[15, None], [14, "h"]],
                [[18, None], [17, "h"]],
                [[19, None], [18, "h"]],
                [[20, None], [19, "h"]],
                [[22, None], [21, "h"]],
                [[23, None], [22, "h"]],
                [[27, None], [26, "h"]],
            ],
            "lines_only_on_base": [13],
            "lines_only_on_head": [],
        }
        deserialized_file = self.comparison_report.deserialize_file(file)
        assert deserialized_file == ImpactedFile(
            file_name="words.js",
            base_name="flag2/words.js",
            head_name="flag2/words.js",
            base_coverage=None,
            head_coverage=ReportTotals(
                files=0,
                lines=0,
                hits=12,
                misses=1,
                partials=1,
                coverage=85.71428571428571,
                branches=3,
                methods=5,
                messages=0,
                sessions=0,
                complexity=0,
                complexity_total=0,
                diff=0,
            ),
            patch_coverage=None,
            change_coverage=None,
            misses_in_comparison=1,
        )

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_in_comparison_descending(
        self, read_file
    ):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.MISSES_IN_COMPARISON,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_in_comparison_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.MISSES_IN_COMPARISON,
            }
        }
        impacted_files = self.comparison_report.impacted_files(filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
                misses_in_comparison=1,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_indirect_changes(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {"has_unintended_changes": True}
        impacted_files = self.comparison_report.impacted_files(filters)
        print("oyyyyy", impacted_files)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=2,
                    partials=1,
                    coverage=76.92307692307692,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=35.256410256410255,
                misses_in_comparison=3,
            )
        ]
