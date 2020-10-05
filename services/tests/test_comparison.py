from django.test import TestCase
import asyncio

from unittest.mock import patch, PropertyMock
import pytest

from shared.reports.resources import ReportFile
from shared.reports.types import ReportLine, LineSession
from shared.utils.merge import LineType

from core.tests.factories import CommitFactory
from codecov_auth.tests.factories import OwnerFactory
from services.archive import SerializableReport
from services.comparison import (
    FileComparisonTraverseManager,
    CreateLineComparisonVisitor,
    CreateChangeSummaryVisitor,
    LineComparison,
    FileComparison,
    Comparison,
)


# Pulled from core.tests.factories.CommitFactory files.
# Contents don't actually matter, it's just for providing a format
# compatible with what SerializableReport expects. Used in
# ComparisonTests.
file_data = [
    2,
    [0, 10, 8, 2, 0, '80.00000', 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 8, 2, 0, '80.00000', 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, '50.00000', 0, 0, 0, 0, 0, 0, 0]
]


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
        manager = FileComparisonTraverseManager(
            head_file_eof=3,
            base_file_eof=3
        )

        expected_result = [(1, 1), (2, 2)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_added_lines_adjusts_lines(self):
        # A line added at line 1 -- note header is string values, that's how
        # torngit returns it
        segments = [{"header": ["1", "1", "1", "2"], "lines": ["+"]}]

        manager = FileComparisonTraverseManager(
            head_file_eof=4,
            base_file_eof=3,
            segments=segments
        )

        expected_result = [(None, 1), (1, 2), (2, 3)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_removed_lines_adjusts_lines(self):
        # A line removed at line 1
        segments = [{"header": ["1", "1", "1", "2"], "lines": ["-"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=3,
            base_file_eof=4,
            segments=segments
        )

        expected_result = [(1, None), (2, 1), (3, 2)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_1_line_added_file_adjusts_lines(self):
        segments = [{"header": ["0", "0", "1", ""], "lines": ["+"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=2,
            base_file_eof=0,
            segments=segments
        )

        expected_result = [(None, 1)]

        visitor = LineNumberCollector()
        manager.apply(visitors=[visitor])

        assert visitor.line_numbers == expected_result

    def test_diff_with_1_line_removed_file_adjusts_lines(self):
        segments = [{"header": ["1", "1", "0", ""], "lines": ["-"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=0,
            base_file_eof=2,
            segments=segments
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
        segments = [{"header": [1, 2, 1, 3], "lines": [expected_line_value, "this is another line"]}]
        manager = FileComparisonTraverseManager(segments=segments)
        assert manager.pop_line() == expected_line_value

    def test_pop_line_returns_line_at_head_ln_index_in_src_if_not_in_segment(self):
        expected_line_value = "a line from src!"
        manager = FileComparisonTraverseManager(head_file_eof=2, src=[expected_line_value])
        assert manager.pop_line() == expected_line_value

    def test_traversing_diff_returns_true_if_head_ln_within_segment_at_position_0(self):
        manager = FileComparisonTraverseManager(segments=[{"header": ["1", "6", "12", "4"]}])
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
        manager = FileComparisonTraverseManager(segments=[{"header": ["4", "43", "4", "3"]}])
        manager.head_ln = 7
        manager.base_ln = 44
        assert manager.traversing_diff() is True

    def test_traverse_finished_returns_false_even_both_line_counters_at_eof_and_traversing_diff(self):
        # This accounts for an edge case wherein you remove a multi-line expression
        # (which codecov counts as a single line, coverage-wise) at the
        # end of a file. The git-diff counts these as multiple lines, so
        # in order to not truncate the diff we need to continue popping
        # lines off the segment even of line counters are technically both
        # at EOF.
        manager = FileComparisonTraverseManager(
            head_file_eof=7,
            base_file_eof=43,
            segments=[{"header": ["4", "43", "4", "3"]}]
        )

        manager.base_ln = 45 # higher than eof, but still traversing_diff
        manager.head_ln = 7  # highest it can go in this segment

        assert manager.traverse_finished() is False

    def test_no_indexerror_if_basefile_longer_than_headfile_and_src_provided(self):
        manager = FileComparisonTraverseManager(
            head_file_eof=3,
            base_file_eof=4,
            src=["hey"] * 2 # head file eof minus 1, which is the typical case
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
        segments = [{"header": ["3", "4", "3", "4"], "lines": ["-Pro Team (billed monthly)", "+Pro Team"]}]
        manager = FileComparisonTraverseManager(
            head_file_eof=2,
            base_file_eof=2,
            segments=segments
        )

        visitor = LineNumberCollector()
        manager.apply([visitor])
        assert visitor.line_numbers == [(1, 1), (2, 2), (3, None), (None, 3)]


class CreateLineComparisonVisitorTests(TestCase):
    def setUp(self):
        self.head_file = ReportFile("file1", lines=[[0, '', [], 0, 0], None, [0, '', [], 0, 0]])
        self.base_file = ReportFile("file1", lines=[None, [0, '', [], 0, 0], None, [0, '', [], 0, 0]])

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

    def test_appends_line_comparison_with_no_base_line_if_no_base_file_or_line_not_in_base_file(self):
        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(100, 1, '', False) # 100 is not a line in the base file
        assert visitor.lines[0].base_line is None

        visitor.base_file = None
        visitor(2, 1, '', False) # all valid line numbers, but still expect none without base_file
        assert visitor.lines[1].base_line is None

    def test_appends_line_comparison_with_no_head_line_if_no_head_file_or_line_not_in_head_file(self):
        visitor = CreateLineComparisonVisitor(self.base_file, self.head_file)
        visitor(2, 100, '', False)
        assert visitor.lines[0].head_line is None

        visitor.head_file = None
        visitor(1, 2, '', False)
        assert visitor.lines[1].head_line is None


class CreateChangeSummaryVisitorTests(TestCase):
    def setUp(self):
        self.head_file = ReportFile("file1", lines=[[1, '', [], 0, 0]])
        self.base_file = ReportFile("file1", lines=[[0, '', [], 0, 0]])

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
        lc = LineComparison([0, '', [], 0, 0], [0, '', [], 0, 0], base_ln, head_ln, "", False)
        assert lc.number == {"base": base_ln, "head": head_ln}

    def test_number_shows_none_for_base_if_added(self):
        head_ln = 4
        lc = LineComparison(None, [0, '', [], 0, 0], 0, head_ln, "+", False)
        assert lc.number == {"base": None, "head": head_ln}

    def test_number_shows_none_for_head_if_removed(self):
        base_ln = 3
        lc = LineComparison([0, '', [], 0, 0], None, base_ln, 0, "-", False)
        assert lc.number == {"base": base_ln, "head": None}

    def test_coverage_shows_coverage_for_base_and_head(self):
        base_cov, head_cov = 0, 1
        lc = LineComparison([base_cov, '', [], 0, 0], [head_cov, '', [], 0, 0], 0, 0, "", False)
        assert lc.coverage == {"base": LineType.miss, "head": LineType.hit}

    def test_coverage_shows_none_for_base_if_added(self):
        head_cov = 1
        lc = LineComparison(None, [head_cov, '', [], 0, 0], 0, 0, "+", False)
        assert lc.coverage == {"base": None, "head": LineType.hit}

    def test_coverage_shows_none_for_head_if_removed(self):
        base_cov = 0
        lc = LineComparison([base_cov, '', [], 0, 0], None, 0, 0, "-", False)
        assert lc.coverage == {"base": LineType.miss, "head": None}

    def test_sessions_returns_sessions_hit_in_head(self):
        lc = LineComparison(
            None,
            [
                1,
                '',
                [
                    [0, 1, 0, 0, 0],
                    [1, 2, 0, 0, 0],
                    [2, 1, 0, 0, 0]
                ],
                0,
                0
            ],
            0, 0, "", False
        )

        assert lc.sessions == 2

    def test_sessions_returns_none_if_no_coverage(self):
        lc = LineComparison(
            None,
            [
                0,
                '',
                [
                    [0, 0, 0, 0, 0]
                ],
                0,
                0
            ],
            0, 0, "", False
        )
        assert lc.sessions is None


class FileComparisonTests(TestCase):
    def setUp(self):
        self.file_comparison = FileComparison(
            head_file=ReportFile("file1"),
            base_file=ReportFile("file1")
        )

    def test_name_shows_name_for_base_and_head(self):
        assert self.file_comparison.name == {
            "base": self.file_comparison.base_file.name,
            "head": self.file_comparison.head_file.name
        }

    def test_name_none_if_base_or_head_if_files_none(self):
        self.file_comparison.head_file = None
        assert self.file_comparison.name == {
            "base": self.file_comparison.base_file.name,
            "head": None
        }

        self.file_comparison.base_file = None
        assert self.file_comparison.name == {
            "base": None,
            "head": None
        }

    def test_totals_shows_totals_for_base_and_head(self):
        assert self.file_comparison.totals == {
            "base": self.file_comparison.base_file.totals,
            "head": self.file_comparison.head_file.totals
        }

    def test_totals_base_is_none_if_missing_basefile(self):
        self.file_comparison.base_file = None
        assert self.file_comparison.totals == {
            "base": None,
            "head": self.file_comparison.head_file.totals
        }

    def test_totals_head_is_none_if_missing_headfile(self):
        self.file_comparison.head_file = None
        assert self.file_comparison.totals == {
            "base": self.file_comparison.base_file.totals,
            "head": None
        }

    def test_totals_includes_diff_totals_if_diff(self):
        totals = "these are the totals"
        self.file_comparison.diff_data = {
          "totals": totals
        }
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
        head_lines = [[1, '', [], 0, None], ["1/2", '', [], 0, None], [1, '', [], 0, None]]
        base_lines = [[0, '', [], 0, None], [1, '', [], 0, None], [0, '', [], 0, None]]

        first_line_val = "unchanged line from src"
        second_line_val = "+this is an added line"
        third_line_val = "-this is a removed line"
        last_line_val = "this is the third line"

        segment = {"header": ["2", "2", "2", "2"], "lines": [second_line_val, third_line_val]}
        src = [first_line_val, "this is an added line", last_line_val]

        self.file_comparison.head_file._lines = head_lines
        self.file_comparison.base_file._lines = base_lines
        self.file_comparison.diff_data = {"segments": [segment]}
        self.file_comparison.src = src

        assert self.file_comparison.lines[0].value == first_line_val
        assert self.file_comparison.lines[0].number == {"base": 1, "head": 1}
        assert self.file_comparison.lines[0].coverage == {"base": LineType.miss, "head": LineType.hit}

        assert self.file_comparison.lines[1].value == second_line_val
        assert self.file_comparison.lines[1].number == {"base": None, "head": 2}
        assert self.file_comparison.lines[1].coverage == {"base": None, "head": LineType.partial}

        assert self.file_comparison.lines[2].value == third_line_val
        assert self.file_comparison.lines[2].number == {"base": 2, "head": None}
        assert self.file_comparison.lines[2].coverage == {"base": LineType.hit, "head": None}

        assert self.file_comparison.lines[3].value == last_line_val
        assert self.file_comparison.lines[3].number == {"base": 3, "head": 3}
        assert self.file_comparison.lines[3].coverage == {"base": LineType.miss, "head": LineType.hit}

    def test_change_summary(self):
        head_lines = [[1, '', [], 0, None], ["3/4", '', [], 0, None], [1, '', [], 0, None]]
        base_lines = [[0, '', [], 0, None], [1, '', [], 0, None], [0, '', [], 0, None]]

        first_line_val = "unchanged line from src"
        second_line_val = "+this is an added line"
        third_line_val = "-this is a removed line"
        last_line_val = "this is the third line"

        segment = {"header": ["2", "2", "2", "2"], "lines": [second_line_val, third_line_val]}
        src = [first_line_val, "this is an added line", last_line_val]

        self.file_comparison.head_file._lines = head_lines
        self.file_comparison.base_file._lines = base_lines
        self.file_comparison.diff_data = {"segments": [segment]}
        self.file_comparison.src = src

        assert self.file_comparison.change_summary == {"hits": 2, "misses": -2}


@patch('services.comparison.Comparison.git_comparison', new_callable=PropertyMock)
@patch('services.comparison.Comparison.head_report', new_callable=PropertyMock)
@patch('services.comparison.Comparison.base_report', new_callable=PropertyMock)
class ComparisonTests(TestCase):
    def setUp(self):
        owner = OwnerFactory()
        base, head = CommitFactory(author=owner), CommitFactory(author=owner)
        self.comparison = Comparison(base, head, owner)

    def test_files_gets_file_comparison_for_each_file_in_head_report(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        head_report_files = {"file1": file_data, "file2": file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)
        base_report_mock.return_value = SerializableReport(files={})
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        assert sum(1 for x in  self.comparison.files) == 2
        for fc in self.comparison.files:
            assert isinstance(fc, FileComparison)
            assert fc.head_file.name in head_report_files
            assert fc.base_file is None

    def test_get_file_comparison_adds_in_file_from_base_report_if_exists(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        files = {"both.py": file_data}
        base_report_mock.return_value = SerializableReport(files=files)
        head_report_mock.return_value = SerializableReport(files=files)

        fc = self.comparison.get_file_comparison("both.py")
        assert fc.head_file.name == "both.py"
        assert fc.base_file.name == "both.py"

    def test_get_file_comparison_accounts_for_renamed_files(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        file_name = "myfile.py"
        previous_name = "previous.py"

        base_report_files = {previous_name: file_data}
        base_report_mock.return_value = SerializableReport(files=base_report_files)

        head_report_files = {file_name : file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {
            "diff": {
                "files": {
                    file_name: {
                        "before": previous_name,
                        "segments": []
                    }
                }
            },
            "commits": []
        }

        fc = self.comparison.get_file_comparison(file_name)
        assert fc.head_file.name == file_name
        assert fc.base_file.name == previous_name

    def test_get_file_comparison_includes_diff_data_if_exists(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        file_name = "f"
        diff_data = {
            "segments": [{
                "header": ["4", "6", "7", "3"],
                "lines": []
            }],
            "stats": {"added": 3, "removed": 2}
        }

        base_report_mock.return_value = SerializableReport(files={})

        head_report_files = {file_name : file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {
            "diff": {
                "files": {file_name: diff_data}
            }
        }

        fc = self.comparison.get_file_comparison(file_name)
        assert fc.diff_data == diff_data

    @patch('services.repo_providers.RepoProviderService.get_adapter')
    def test_get_file_comparison_includes_src_if_with_src_is_true(
        self,
        mocked_comparison_adapter,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        from internal_api.tests.views.test_compare_viewset import MockedComparisonAdapter
        src = b"two\nlines"
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        mocked_comparison_adapter.return_value = MockedComparisonAdapter(
            {"diff": {"files": {}}},
            test_lines=src
        )

        file_name = "f"

        base_report_mock.return_value = SerializableReport(files={})
        head_report_files = {file_name : file_data}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        fc = self.comparison.get_file_comparison(file_name, with_src=True)
        assert fc.src == ["two", "lines"]

    def test_get_file_comparison_with_no_base_report_doesnt_crash(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        files = {"both.py": file_data}
        base_report_mock.return_value = None
        head_report_mock.return_value = SerializableReport(files=files)

        fc = self.comparison.get_file_comparison("both.py")
        assert fc.head_file.name == "both.py"

    @pytest.mark.xfail #TODO(pierce): investigate this feature
    def test_files_adds_deleted_files_that_were_tracked_in_base_report(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        deleted_file_name = "deleted.py"
        base_report_files = {deleted_file_name: file_data}
        base_report_mock.return_value = SerializableReport(files=base_report_files)

        head_report_files = {}
        head_report_mock.return_value = SerializableReport(files=head_report_files)

        git_comparison_mock.return_value = {
            "diff": {
                "files": {
                    deleted_file_name: {"type": "deleted"}
                }
            },
            "commits": []
        }

        assert self.comparison.files[0].base_file.name == deleted_file_name
        assert self.comparison.files[0].head_file is None
        assert self.comparison.files[0].diff_data == {"type": "deleted"}

    def test_totals_returns_head_totals_if_exists(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.return_value = SerializableReport()

        assert self.comparison.totals["head"] == head_report_mock.return_value.totals
        assert self.comparison.totals["base"] is None

    def test_totals_returns_head_totals_if_exists(
        self,
        base_report_mock,
        head_report_mock,
        git_comparison_mock
    ):
        head_report_mock.return_value = None
        base_report_mock.return_value = SerializableReport()

        assert self.comparison.totals["base"] == base_report_mock.return_value.totals
        assert self.comparison.totals["head"] is None


@patch('services.comparison.Comparison.git_comparison', new_callable=PropertyMock)
@patch('services.archive.ReportService.build_report_from_commit')
class ComparisonHeadReportTests(TestCase):
    def setUp(self):
        owner = OwnerFactory()
        base, head = CommitFactory(author=owner), CommitFactory(author=owner)
        self.comparison = Comparison(base, head, owner)

    @patch('services.archive.SerializableReport.apply_diff')
    def test_head_report_calls_apply_diff(
        self,
        apply_diff_mock,
        build_report_from_commit_mock,
        git_comparison_mock
    ):
        build_report_from_commit_mock.return_value = SerializableReport(files={"f": file_data})
        git_comparison_mock.return_value = {"diff": {"files": {}}}

        # should be called when invoking this property
        self.comparison.head_report

        apply_diff_mock.assert_called_once_with(git_comparison_mock.return_value["diff"])


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
        self.comparison = Comparison(base, head, owner)
        asyncio.set_event_loop(asyncio.new_event_loop())

    def test_returns_true_if_reverse_comparison_has_commits(self, get_adapter_mock):
        commits = ["a", "b"]
        get_adapter_mock.return_value = ComparisonHasUnmergedBaseCommitsTests.MockFetchDiffCoro(commits)
        assert self.comparison.has_unmerged_base_commits is True

    def test_returns_false_if_reverse_comparison_has_one_commit_or_less(self, get_adapter_mock):
        commits = ["a"]
        get_adapter_mock.return_value = ComparisonHasUnmergedBaseCommitsTests.MockFetchDiffCoro(commits)
        assert self.comparison.has_unmerged_base_commits is False
