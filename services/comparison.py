import asyncio
import copy
import functools
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import minio
import pytz
import shared.reports.api_report_service as report_service
from asgiref.sync import async_to_sync
from django.db.models import Prefetch, QuerySet
from django.utils.functional import cached_property
from shared.api_archive.archive import ArchiveService
from shared.helpers.yaml import walk
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType, line_type

from compare.models import CommitComparison
from core.models import Commit, Pull
from reports.models import CommitReport
from services import ServiceException
from services.redis_configuration import get_redis_connection
from services.repo_providers import RepoProviderService
from utils.config import get_config

log = logging.getLogger(__name__)


redis = get_redis_connection()


MAX_DIFF_SIZE = 170


def _is_added(line_value):
    return line_value and line_value[0] == "+"


def _is_removed(line_value):
    return line_value and line_value[0] == "-"


class ComparisonException(ServiceException):
    @property
    def message(self):
        return str(self)


class MissingComparisonCommit(ComparisonException):
    pass


class MissingComparisonReport(ComparisonException):
    pass


class FirstPullRequest:
    message = "This is the first pull request for this repository"


class FileComparisonTraverseManager:
    """
    The FileComparisonTraverseManager uses the visitor-pattern to execute a series
    of arbitrary actions on each line in a FileComparison. The main entrypoint to
    this class is the '.apply()' method, which is the only method client code should invoke.
    """

    def __init__(self, head_file_eof=0, base_file_eof=0, segments=[], src=[]):
        """
        head_file_eof -- end-line of the head_file we are traversing, plus 1
        base_file_eof -- same as above, for base_file

        ^^ Generally client code should supply both, except in a couple cases:
          1. The file is newly tracked. In this case, there is no base file, so we should
             iterate only over the head file lines.
          2. The file is deleted. As of right now (4/2/2020), we don't show deleted files in
             comparisons, but if we were to support that, we would not supply a head_file_eof
             and instead only iterate over lines in the base file.

        segments -- these come from the provider API response related to the comparison, and
            constitute the 'diff' between the base and head references. Each segment takes this form:

            {
                "header": [
                    base reference offset,
                    number of lines in file-segment before changes applied,
                    head reference offset,
                    number of lines in file-segment after changes applied
                ],
                "lines": [ # line values for lines in the diff
                  "+this is an added line",
                  "-this is a removed line",
                  "this line is unchanged in the diff",
                  ...
                ]
            }

            The segment["header"], also known as the hunk-header (https://en.wikipedia.org/wiki/Diff#Unified_format),
            is an array of strings, which is why we have to use the int() builtin function
            to compare with self.head_ln and self.base_ln. It is used by this algorithm to
              1. Set initial values for the self.base_ln and self.head_ln line-counters, and
              2. Detect if self.base and/or self.head refer to lines in the diff at any given time

            This algorithm relies on the fact that segments are returned in ascending
            order for each file, which means that the "nearest" segment to the current line
            being traversed is located at segments[0].

        src -- this is the source code of the file at the head-reference, where each line
            is a cell in the array. If we are not traversing a segment, and src is provided,
            the line value passed to the visitors will be the line at src[self.head_ln - 1].
        """
        self.head_file_eof = head_file_eof
        self.base_file_eof = base_file_eof
        self.segments = copy.deepcopy(segments)
        self.src = src

        if self.segments:
            # Base offsets can be 0 if files are added or removed
            self.base_ln = min(1, int(self.segments[0]["header"][0]))
            self.head_ln = min(1, int(self.segments[0]["header"][2]))
        else:
            self.base_ln, self.head_ln = 1, 1

    def traverse_finished(self):
        if self.segments:
            return False
        if self.src:
            return self.head_ln > len(self.src)
        return self.head_ln >= self.head_file_eof and self.base_ln >= self.base_file_eof

    def traversing_diff(self):
        if self.segments == []:
            return False

        base_ln_within_offset = (
            int(self.segments[0]["header"][0])
            <= self.base_ln
            < int(self.segments[0]["header"][0])
            + int(self.segments[0]["header"][1] or 1)
        )
        head_ln_within_offset = (
            int(self.segments[0]["header"][2])
            <= self.head_ln
            < int(self.segments[0]["header"][2])
            + int(self.segments[0]["header"][3] or 1)
        )
        return base_ln_within_offset or head_ln_within_offset

    def pop_line(self):
        if self.traversing_diff():
            return self.segments[0]["lines"].pop(0)

        if self.src:
            return self.src[self.head_ln - 1]

    def apply(self, visitors):
        """
        Traverses the lines in a file comparison while accounting for the diff.
        If a line only appears in the base file (removed in head), it is prefixed
        with '-', and we only increment self.base_ln. If a line only appears in
        the head file, it is newly added and prefixed with '+', and we only
        increment self.head_ln.

        visitors -- A list of visitors applied to each line.
        """
        while not self.traverse_finished():
            line_value = self.pop_line()
            is_diff = self.traversing_diff()

            for visitor in visitors:
                visitor(
                    None if is_diff and _is_added(line_value) else self.base_ln,
                    None if is_diff and _is_removed(line_value) else self.head_ln,
                    line_value,
                    is_diff,  # TODO(pierce): remove when upon combining diff + changes tabs in UI
                )

            if is_diff and _is_added(line_value):
                self.head_ln += 1
            elif is_diff and _is_removed(line_value):
                self.base_ln += 1
            else:
                self.head_ln += 1
                self.base_ln += 1

            if self.segments and not self.segments[0]["lines"]:
                # Either the segment has no lines (and is therefore of no use)
                # or all lines have been popped and visited, which means we are
                # done traversing it
                self.segments.pop(0)


class FileComparisonVisitor:
    """
    Abstract class with a convenience method for getting lines amongst
    all the edge cases.
    """

    def _get_line(self, report_file, ln):
        """
        Kindof a hacky way to bypass the dataclasses used in `reports`
        library, because they are extremely slow. This basically copies
        some logic from ReportFile.get and ReportFile._line, which work
        together to take an index and turn it into a ReportLine. Here
        we do something similar, but just return the underlying array instead.
        Not sure if this will be the final solution.

        Note: the underlying array representation cn be seen here:
        https://github.com/codecov/shared/blob/master/shared/reports/types.py#L75
        The index in the array representation is 1-1 with the index of the
        dataclass attribute for ReportLine.
        """
        if report_file is None or ln is None:
            return None

        # copied from ReportFile.get
        try:
            line = report_file._lines[ln - 1]
        except IndexError:
            return None

        # copied from ReportFile._line, minus dataclass instantiation
        if line:
            if isinstance(line, list):
                return line
            else:
                # these are old versions
                # note:(pierce) ^^ this comment is copied, not sure what it means
                return json.loads(line)

    def _get_lines(self, base_ln, head_ln):
        base_line = self._get_line(self.base_file, base_ln)
        head_line = self._get_line(self.head_file, head_ln)
        return base_line, head_line

    def __call__(self, base_ln, head_ln, value, is_diff):
        pass


class CreateLineComparisonVisitor(FileComparisonVisitor):
    """
    A visitor that creates LineComparisons, and stores the
    result in self.lines. Only operates on lines that have
    code-values derived from segments or src in FileComparisonTraverseManager.
    """

    def __init__(self, base_file, head_file):
        self.base_file, self.head_file = base_file, head_file
        self.lines = []

    def __call__(self, base_ln, head_ln, value, is_diff):
        if value is None:
            return

        base_line, head_line = self._get_lines(base_ln, head_ln)

        self.lines.append(
            LineComparison(
                base_line=base_line,
                head_line=head_line,
                base_ln=base_ln,
                head_ln=head_ln,
                value=value,
                is_diff=is_diff,
            )
        )


class CreateChangeSummaryVisitor(FileComparisonVisitor):
    """
    A visitor for summarizing the "unexpected coverage changes"
    to a certain file. We specifically ignore lines that are changed
    in the source code, which are prefixed with '+' or '-'. Result
    is stored in self.summary.
    """

    def __init__(self, base_file, head_file):
        self.base_file, self.head_file = base_file, head_file
        self.summary = Counter()
        self.coverage_type_map = {
            LineType.hit: "hits",
            LineType.miss: "misses",
            LineType.partial: "partials",
        }

    def _update_summary(self, base_line, head_line):
        """
        Updates the change summary based on the coverage type (0
        for miss, 1 for hit, 2 for partial) found at index 0 of the
        line-array.
        """
        self.summary[self.coverage_type_map[line_type(base_line[0])]] -= 1
        self.summary[self.coverage_type_map[line_type(head_line[0])]] += 1

    def __call__(self, base_ln, head_ln, value, is_diff):
        if value and value[0] in ["+", "-"]:
            return

        base_line, head_line = self._get_lines(base_ln, head_ln)
        if base_line is None or head_line is None:
            return

        if line_type(base_line[0]) == line_type(head_line[0]):
            return

        self._update_summary(base_line, head_line)


class LineComparison:
    def __init__(self, base_line, head_line, base_ln, head_ln, value, is_diff):
        self.base_line = base_line
        self.head_line = head_line
        self.head_ln = head_ln
        self.base_ln = base_ln
        self.value = value
        self.is_diff = is_diff

        self.added = is_diff and _is_added(value)
        self.removed = is_diff and _is_removed(value)

    @property
    def number(self):
        return {
            "base": self.base_ln if not self.added else None,
            "head": self.head_ln if not self.removed else None,
        }

    @property
    def coverage(self):
        return {
            "base": None
            if self.added or not self.base_line
            else line_type(self.base_line[0]),
            "head": None
            if self.removed or not self.head_line
            else line_type(self.head_line[0]),
        }

    @cached_property
    def head_line_sessions(self) -> Optional[List[tuple]]:
        if self.head_line is None:
            return None

        # `head_line` is the tuple representation of a `shared.reports.types.ReportLine`
        # it has the following shape:
        # (coverage, type, sessions, messages, complexity, datapoints)

        # each session is a tuple representation of a `shared.reports.types.LineSession`
        # is has the following shape:
        # (id, coverage, branches, partials, complexity)
        sessions = self.head_line[2]

        return sessions

    @cached_property
    def hit_count(self) -> Optional[int]:
        if self.head_line_sessions is None:
            return None

        hit_count = 0
        for id, coverage, *rest in self.head_line_sessions:
            if line_type(coverage) == LineType.hit:
                hit_count += 1
        if hit_count > 0:
            return hit_count

    @cached_property
    def hit_session_ids(self) -> Optional[List[int]]:
        if self.head_line_sessions is None:
            return None

        ids = []
        for id, coverage, *rest in self.head_line_sessions:
            if line_type(coverage) == LineType.hit:
                ids.append(id)
        if len(ids) > 0:
            return ids


class Segment:
    """
    A segment represents a contiguous subset of lines in a file where either
    the coverage has changed or the code has changed (i.e. is part of a diff).
    """

    # additional lines included before and after each segment
    padding_lines = 3

    # max distance between lines with coverage changes in a single segment
    line_distance = 6

    @classmethod
    def segments(cls, file_comparison):
        lines = file_comparison.lines

        # line numbers of interest (i.e. coverage changed or code changed)
        line_numbers = []
        for idx, line in enumerate(lines):
            if (
                line.coverage["base"] != line.coverage["head"]
                or line.added
                or line.removed
            ):
                line_numbers.append(idx)

        segmented_lines = []
        if len(line_numbers) > 0:
            segmented_lines, last = [[]], None
            for line_number in line_numbers:
                if last is None or line_number - last <= cls.line_distance:
                    segmented_lines[-1].append(line_number)
                else:
                    segmented_lines.append([line_number])
                last = line_number

        segments = []
        for group in segmented_lines:
            # padding lines before first line of interest
            start_line_number = group[0] - cls.padding_lines
            start_line_number = max(start_line_number, 0)
            # padding lines after last line of interest
            end_line_number = group[-1] + cls.padding_lines
            end_line_number = min(end_line_number, len(lines) - 1)

            segment = cls(lines[start_line_number : end_line_number + 1])
            segments.append(segment)

        return segments

    def __init__(self, lines):
        self._lines = lines

    @property
    def header(self):
        base_start = None
        head_start = None
        num_removed = 0
        num_added = 0
        num_context = 0

        for line in self.lines:
            if base_start is None and line.number["base"] is not None:
                base_start = int(line.number["base"])
            if head_start is None and line.number["head"] is not None:
                head_start = int(line.number["head"])
            if line.added:
                num_added += 1
            elif line.removed:
                num_removed += 1
            else:
                num_context += 1

        return (
            base_start or 0,
            num_context + num_removed,
            head_start or 0,
            num_context + num_added,
        )

    @property
    def lines(self):
        return self._lines

    @property
    def has_diff_changes(self):
        for line in self.lines:
            if line.added or line.removed:
                return True
        return False

    @property
    def has_unintended_changes(self):
        for line in self.lines:
            head_coverage = line.coverage["base"]
            base_coverage = line.coverage["head"]
            if not (line.added or line.removed) and (base_coverage != head_coverage):
                return True
        return False

    def remove_unintended_changes(self):
        filtered = []
        for line in self._lines:
            base_cov = line.coverage["base"]
            head_cov = line.coverage["head"]
            if (line.added or line.removed) or (base_cov == head_cov):
                filtered.append(line)
        self._lines = filtered


class FileComparison:
    def __init__(
        self,
        base_file,
        head_file,
        diff_data=None,
        src=[],
        bypass_max_diff=False,
        should_search_for_changes=None,
    ):
        """
        comparison -- the enclosing Comparison object that owns this FileComparison

        base_file -- the ReportFile for this file from the base report

        head_file -- the ReportFile for this file from the head report

        diff_data -- the git-comparison between the base and head references in the instantiation
            Comparison object. fields include:

            stats: -- {"added": number of added lines, "removed": number of removed lines}
            segments: (described in detail in the FileComparisonTraverseManager docstring)
            before: the name of this file in the base reference, if different from name in head ref

            If this file is unchanged in the comparison between base and head, the default will be used.

        src -- The full source of the file in the head reference. Used in FileComparisonTraverseManager
            to join src-code with coverage data. Default is used when retrieving full comparison,
            whereas full-src is serialized when retrieving individual file comparison.

        bypass_max_diff -- configuration paramater that tells this class to ignore max-diff truncating.
            default is used when retrieving full comparison; True is passed when fetching individual
            file comparison.

        should_search_for_changes -- flag that indicates if this FileComparison has unexpected coverage changes,
            according to a value cached during asynchronous processing. Has three values:
            1. True - indicates this FileComparison has unexpected coverage changes according to worker,
                and we should process the lines in this FileComparison using FileComparisonTraverseManager
                to calculate a change summary.
            2. False - indicates this FileComparison does not have unexpected coverage changes according to
                worker, and we should not traverse this file or calculate a change summary.
            3. None (default) - indicates we do not have information cached from worker to rely on here
                (no value in cache), so we need to traverse this FileComparison and calculate a change
                summary to find out.
        """
        self.base_file = base_file
        self.head_file = head_file
        self.diff_data = diff_data
        self.src = src

        # Some extra fields for truncating large diffs in the initial response
        self.total_diff_length = (
            functools.reduce(
                lambda a, b: a + b,
                [len(segment["lines"]) for segment in self.diff_data["segments"]],
            )
            if self.diff_data is not None and self.diff_data.get("segments")
            else 0
        )

        self.bypass_max_diff = bypass_max_diff
        self.should_search_for_changes = should_search_for_changes

    @property
    def name(self):
        return {
            "base": self.base_file.name if self.base_file is not None else None,
            "head": self.head_file.name if self.head_file is not None else None,
        }

    @property
    def totals(self):
        head_totals = self.head_file.totals if self.head_file is not None else None

        # The call to '.apply_diff()' in 'Comparison.head_report' stores diff totals
        # for each file in the diff_data for that file (in a field called 'totals').
        # Here we pass this along to the frontend by assigning the diff totals
        # to the head_totals' 'diff' attribute. It is absolutely worth considering
        # modifying the behavior of shared.reports to implement something similar.
        diff_totals = None
        if head_totals and self.diff_data:
            diff_totals = self.diff_data.get("totals")
            head_totals.diff = diff_totals or 0

        return {
            "base": self.base_file.totals if self.base_file is not None else None,
            "head": head_totals,
            "diff": diff_totals,
        }

    @property
    def has_diff(self):
        return self.diff_data is not None

    @property
    def stats(self):
        return self.diff_data["stats"] if self.diff_data else None

    @cached_property
    def _calculated_changes_and_lines(self):
        """
        Applies visitors to the file to generate response data (line comparison representations
        and change summary). Only applies visitors if

          1. The file has a diff or src, in which case we need to generate response data for it anyway, or
          2. The should_search_for_changes flag is defined (not None) and is True

        This limitation improves performance by limiting searching for changes to only files that
        have them.
        """
        change_summary_visitor = CreateChangeSummaryVisitor(
            self.base_file, self.head_file
        )
        create_lines_visitor = CreateLineComparisonVisitor(
            self.base_file, self.head_file
        )

        if self.diff_data or self.src or self.should_search_for_changes is not False:
            FileComparisonTraverseManager(
                head_file_eof=self.head_file.eof if self.head_file is not None else 0,
                base_file_eof=self.base_file.eof if self.base_file is not None else 0,
                segments=self.diff_data["segments"]
                if self.diff_data and "segments" in self.diff_data
                else [],
                src=self.src,
            ).apply([change_summary_visitor, create_lines_visitor])

        return change_summary_visitor.summary, create_lines_visitor.lines

    @cached_property
    def change_summary(self):
        return self._calculated_changes_and_lines[0]

    @property
    def has_changes(self):
        return any(self.change_summary.values())

    @cached_property
    def lines(self):
        if self.total_diff_length > MAX_DIFF_SIZE and not self.bypass_max_diff:
            return None
        return self._calculated_changes_and_lines[1]

    @cached_property
    def segments(self):
        return Segment.segments(self)


class Comparison(object):
    def __init__(self, user, base_commit, head_commit):
        # TODO: rename to owner
        self.user = user
        self._base_commit = base_commit
        self._head_commit = head_commit

    def validate(self):
        # make sure head and base reports exist (will throw an error if not)
        self.head_report
        self.base_report

    @cached_property
    def base_commit(self):
        return self._base_commit

    @cached_property
    def head_commit(self):
        return self._head_commit

    @cached_property
    def files(self):
        for file_name in self.head_report.files:
            yield self.get_file_comparison(file_name)

    def get_file_comparison(self, file_name, with_src=False, bypass_max_diff=False):
        head_file = self.head_report.get(file_name)
        diff_data = self.git_comparison["diff"]["files"].get(file_name)

        if self.base_report is not None:
            base_file = self.base_report.get(file_name)
            if base_file is None and diff_data:
                base_file = self.base_report.get(diff_data.get("before"))
        else:
            base_file = None

        if with_src:
            adapter = RepoProviderService().get_adapter(
                owner=self.user, repo=self.base_commit.repository
            )
            file_content = async_to_sync(adapter.get_source)(
                file_name, self.head_commit.commitid
            )["content"]
            # make sure the file is str utf-8
            if not isinstance(file_content, str):
                file_content = str(file_content, "utf-8")
            src = file_content.splitlines()
        else:
            src = []

        return FileComparison(
            base_file=base_file,
            head_file=head_file,
            diff_data=diff_data,
            src=src,
            bypass_max_diff=bypass_max_diff,
        )

    @property
    def git_comparison(self):
        return self._fetch_comparison[0]

    @cached_property
    def base_report(self):
        try:
            return report_service.build_report_from_commit(self.base_commit)
        except minio.error.S3Error as e:
            if e.code == "NoSuchKey":
                raise MissingComparisonReport("Missing base report")
            else:
                raise e

    @cached_property
    def head_report(self):
        try:
            report = report_service.build_report_from_commit(self.head_commit)
        except minio.error.S3Error as e:
            if e.code == "NoSuchKey":
                raise MissingComparisonReport("Missing head report")
            else:
                raise e

        # Return the old report if the github API call fails for any reason
        try:
            report.apply_diff(self.git_comparison["diff"])
        except Exception:
            pass
        return report

    @cached_property
    def has_different_number_of_head_and_base_sessions(self):
        log.info("has_different_number_of_head_and_base_sessions - Start")
        head_sessions = self.head_report.sessions
        base_sessions = self.base_report.sessions
        log.info(
            f"has_different_number_of_head_and_base_sessions - Retrieved sessions - head {len(head_sessions)} / base {len(base_sessions)}"
        )
        # We're treating this case as false since considering CFF's complicates the logic
        if self._has_cff_sessions(head_sessions) or self._has_cff_sessions(
            base_sessions
        ):
            return False
        return len(head_sessions) != len(base_sessions)

    # I feel this method should belong to the API Report class, but we're thinking of getting rid of that class soon
    # In truth, this should be in the shared.Report class
    def _has_cff_sessions(self, sessions) -> bool:
        log.info(f"_has_cff_sessions - sessions count {len(sessions)}")
        for session in sessions.values():
            if session.session_type.value == "carriedforward":
                log.info("_has_cff_sessions - Found carriedforward")
                return True
        log.info("_has_cff_sessions - No carriedforward")
        return False

    @property
    def totals(self):
        return {
            "base": self.base_report.totals if self.base_report is not None else None,
            "head": self.head_report.totals if self.head_report is not None else None,
            "diff": self.git_comparison["diff"].get("totals"),
        }

    @property
    def git_commits(self):
        return self.git_comparison["commits"]

    @property
    def upload_commits(self):
        """
        Returns the commits that have uploads between base and head.
        :return: Queryset of core.models.Commit objects
        """
        commit_ids = [commit["commitid"] for commit in self.git_commits]
        commits_queryset = Commit.objects.filter(
            commitid__in=commit_ids, repository=self.base_commit.repository
        )
        commits_queryset.exclude(deleted=True)
        return commits_queryset

    @cached_property
    def _fetch_comparison(self):
        """
        Fetches comparison, and caches the result.
        """
        adapter = RepoProviderService().get_adapter(
            self.user, self.base_commit.repository
        )
        comparison_coro = adapter.get_compare(
            self.base_commit.commitid, self.head_commit.commitid
        )

        async def runnable():
            return await asyncio.gather(comparison_coro)

        return async_to_sync(runnable)()

    def flag_comparison(self, flag_name):
        return FlagComparison(self, flag_name)

    @property
    def non_carried_forward_flags(self):
        flags_dict = self.head_report.flags
        return [flag for flag, vals in flags_dict.items() if not vals.carriedforward]


class FlagComparison(object):
    def __init__(self, comparison, flag_name):
        self.comparison = comparison
        self.flag_name = flag_name

    @cached_property
    def head_report(self):
        return self.comparison.head_report.flags.get(self.flag_name)

    @cached_property
    def base_report(self):
        return self.comparison.base_report.flags.get(self.flag_name)

    @cached_property
    def diff_totals(self):
        if self.head_report is None:
            return None
        git_comparison = self.comparison.git_comparison
        return self.head_report.apply_diff(git_comparison["diff"])


@dataclass
class ImpactedFile:
    @dataclass
    class Totals(ReportTotals):
        def __post_init__(self):
            nb_branches = self.hits + self.misses + self.partials
            self.coverage = (100 * self.hits / nb_branches) if nb_branches > 0 else None

    base_name: Optional[str] = None  # will be `None` for created files
    head_name: Optional[str] = None  # will be `None` for deleted files
    file_was_added_by_diff: bool = False
    file_was_removed_by_diff: bool = False
    base_coverage: Optional[Totals] = None  # will be `None` for created files
    head_coverage: Optional[Totals] = None  # will be `None` for deleted files

    # lists of (line number, coverage) tuples
    added_diff_coverage: Optional[List[tuple[int, str]]] = None
    removed_diff_coverage: Optional[List[tuple[int, str]]] = field(default_factory=list)
    unexpected_line_changes: Optional[List[tuple[int, str]]] = field(
        default_factory=list
    )

    lines_only_on_base: List[int] = field(default_factory=list)
    lines_only_on_head: List[int] = field(default_factory=list)

    @classmethod
    def create(cls, **kwargs):
        base_coverage = kwargs.pop("base_coverage")
        head_coverage = kwargs.pop("head_coverage")
        return cls(
            **kwargs,
            base_coverage=ImpactedFile.Totals(**base_coverage)
            if base_coverage
            else None,
            head_coverage=ImpactedFile.Totals(**head_coverage)
            if head_coverage
            else None,
        )

    @cached_property
    def has_diff(self) -> bool:
        """
        Returns `True` if the file has any additions or removals in the diff
        """
        return bool(
            self.added_diff_coverage
            and len(self.added_diff_coverage) > 0
            or self.removed_diff_coverage
            and len(self.removed_diff_coverage) > 0
            or self.file_was_added_by_diff
            or self.file_was_removed_by_diff
        )

    @cached_property
    def has_changes(self) -> bool:
        """
        Returns `True` if the file has any unexpected changes
        """
        return (
            self.unexpected_line_changes is not None
            and len(self.unexpected_line_changes) > 0
        )

    @cached_property
    def misses_count(self) -> int:
        total_misses = 0
        total_misses += self._direct_misses_count
        total_misses += self._unintended_misses_count
        return total_misses

    @cached_property
    def _unintended_misses_count(self) -> int:
        """
        Returns the misses count for a unintended impacted file
        """
        misses = 0

        unexpected_line_changes = self.unexpected_line_changes or []
        for [
            base,
            [head_line_number, head_coverage_value],
        ] in unexpected_line_changes:
            if head_coverage_value == "m":
                misses += 1

        return misses

    @cached_property
    def _direct_misses_count(self) -> int:
        """
        Returns the misses count for a direct impacted file
        """

        misses = 0

        diff_coverage = self.added_diff_coverage or []
        for line_number, line_coverage_value in diff_coverage:
            if line_coverage_value == "m":
                misses += 1

        return misses

    @cached_property
    def patch_coverage(self) -> Optional[Totals]:
        """
        Sums of hits, misses and partials in the diff
        """
        if self.added_diff_coverage and len(self.added_diff_coverage) > 0:
            hits, misses, partials = (0, 0, 0)
            for added_coverage in self.added_diff_coverage:
                [_, type_coverage] = added_coverage
                if type_coverage == "h":
                    hits += 1
                if type_coverage == "m":
                    misses += 1
                if type_coverage == "p":
                    partials += 1

            return ImpactedFile.Totals(hits=hits, misses=misses, partials=partials)

    @cached_property
    def change_coverage(self) -> Optional[float]:
        if (
            self.base_coverage
            and self.base_coverage.coverage
            and self.head_coverage
            and self.head_coverage.coverage
        ):
            return float(
                float(self.head_coverage.coverage or 0)
                - float(self.base_coverage.coverage or 0)
            )

    @cached_property
    def file_name(self) -> Optional[str]:
        if self.head_name:
            parts = self.head_name.split("/")
            return parts[-1]


@dataclass
class ComparisonReport(object):
    """
    This is a wrapper around the data computed by the worker's commit comparison task.
    The raw data is stored in blob storage and accessible via the `report_storage_path`
    on a `CommitComparison`
    """

    commit_comparison: CommitComparison = None

    @cached_property
    def files(self) -> List[ImpactedFile]:
        if not self.commit_comparison.report_storage_path:
            return []

        comparison_data = self._fetch_raw_comparison_data()
        return [
            ImpactedFile.create(**data) for data in comparison_data.get("files", [])
        ]

    def impacted_file(self, path: str) -> Optional[ImpactedFile]:
        for file in self.files:
            if file.head_name == path:
                return file

    @cached_property
    def impacted_files(self) -> List[ImpactedFile]:
        return self.files

    @cached_property
    def impacted_files_with_unintended_changes(self) -> List[ImpactedFile]:
        return [file for file in self.files if file.has_changes]

    @cached_property
    def impacted_files_with_direct_changes(self) -> List[ImpactedFile]:
        return [file for file in self.files if file.has_diff or not file.has_changes]

    def _fetch_raw_comparison_data(self) -> dict:
        """
        Fetches the raw comparison data from storage
        """
        repository = self.commit_comparison.compare_commit.repository
        archive_service = ArchiveService(repository)
        try:
            data = archive_service.read_file(self.commit_comparison.report_storage_path)
            return json.loads(data)
        except Exception:
            log.error(
                "ComparisonReport - couldn't fetch data from storage", exc_info=True
            )
            return {}


class PullRequestComparison(Comparison):
    """
    A Comparison instantiated with a Pull. Contains relevant additional processing
    required for Pulls, including caching of files-with-changes and support for
    'pseudo-comparisons'.
    """

    def __init__(self, user, pull):
        self.pull = pull
        super().__init__(
            user=user,
            # these are lazy loaded in the property methods below
            base_commit=None,
            head_commit=None,
        )

    # TODO: try using the dataloader to fetch the commits before you create this class, and pass those commits
    # to the constructor
    @cached_property
    def base_commit(self):
        try:
            return Commit.objects.defer("_report").get(
                repository=self.pull.repository,
                commitid=self.pull.compared_to
                if self.is_pseudo_comparison
                else self.pull.base,
            )
        except Commit.DoesNotExist:
            raise MissingComparisonCommit("Missing base commit")

    @cached_property
    def head_commit(self):
        try:
            return Commit.objects.defer("_report").get(
                repository=self.pull.repository, commitid=self.pull.head
            )
        except Commit.DoesNotExist:
            raise MissingComparisonCommit("Missing head commit")

    @cached_property
    def _files_with_changes_hash_key(self):
        return "/".join(
            (
                "compare-changed-files",
                self.pull.repository.author.service,
                self.pull.repository.author.username,
                self.pull.repository.name,
                f"{self.pull.pullid}",
            )
        )

    @cached_property
    def _files_with_changes(self):
        try:
            key = self._files_with_changes_hash_key
            changes = json.loads(redis.get(key) or json.dumps(None))
            log.info(
                f"Found {len(changes) if changes else 0} files with changes in cache.",
                extra=dict(repoid=self.pull.repository.repoid, pullid=self.pull.pullid),
            )
            return changes
        except OSError as e:
            log.warning(
                f"Error connecting to redis: {e}",
                extra=dict(repoid=self.pull.repository.repoid, pullid=self.pull.pullid),
            )

    def _set_files_with_changes_in_cache(self, files_with_changes):
        redis.set(
            self._files_with_changes_hash_key,
            json.dumps(files_with_changes),
            ex=86400,  # 1 day in seconds
        )
        log.info(
            f"Stored {len(files_with_changes)} files with changes in cache",
            extra=dict(repoid=self.pull.repository.repoid, pullid=self.pull.pullid),
        )

    @cached_property
    def files(self):
        """
        Overrides the 'files' property to do additional caching of
        'files_with_changes', for future performance improvements.
        """
        files_with_changes = []
        for file_comparison in super().files:
            if file_comparison.change_summary:
                files_with_changes.append(file_comparison.name["head"])
            yield file_comparison
        self._set_files_with_changes_in_cache(files_with_changes)

    def get_file_comparison(self, file_name, with_src=False, bypass_max_diff=False):
        """
        Overrides the 'get_file_comparison' method to set the "should_search_for_changes"
        field.
        """
        file_comparison = super().get_file_comparison(
            file_name, with_src=with_src, bypass_max_diff=bypass_max_diff
        )
        file_comparison.should_search_for_changes = (
            file_name in self._files_with_changes
            if self._files_with_changes is not None
            else None
        )
        return file_comparison

    @cached_property
    def is_pseudo_comparison(self):
        """
        Returns True if this comparison is a pseudo-comparison, False if not.

        Depends on
            1) The repository yaml or app yaml settings allow pseudo_comparisons
            2) the pull request's 'compared_to' field is defined
        """
        return walk(
            _dict=self.pull.repository.yaml,
            keys=("codecov", "allow_pseudo_compare"),
            _else=get_config(("site", "codecov", "allow_pseudo_compare"), default=True),
        ) and bool(self.pull.compared_to)

    @cached_property
    def pseudo_diff(self):
        """
        Returns the diff between the 'self.pull.compared_to' field and the
        'self.pull.base' field.
        """
        adapter = RepoProviderService().get_adapter(self.user, self.pull.repository)
        return async_to_sync(adapter.get_compare)(
            self.pull.compared_to, self.pull.base
        )["diff"]

    @cached_property
    def pseudo_diff_adjusts_tracked_lines(self):
        """
        Returns True if we are doing a pull request pseudo-comparison, and tracked
        lines have changed between the pull's 'base' and 'compared_to' fields. This
        signifies an error-condition for the comparison, I think because if tracked lines
        have been adjusted between the 'base' and 'compared_to' commits, the 'compared_to'
        report can't be substituted for the 'base' report, since it will throw off the
        unexpected coverage change results. If `self.allow_coverage_offests` is True,
        client code can adjust the lines in the base report according to the diff
        with `self.update_base_report_with_pseudo_diff'.

        Ported from the block at: https://github.com/codecov/codecov.io/blob/master/app/handlers/compare.py#L137
        """
        if (
            self.is_pseudo_comparison
            and self.pull.base != self.pull.compared_to
            and self.base_report is not None
            and self.head_report is not None
        ):
            if self.pseudo_diff and self.pseudo_diff.get("files"):
                return self.base_report.does_diff_adjust_tracked_lines(
                    self.pseudo_diff,
                    future_report=self.head_report,
                    future_diff=self.git_comparison["diff"],
                )
        return False

    def update_base_report_with_pseudo_diff(self):
        self.base_report.shift_lines_by_diff(self.pseudo_diff, forward=True)


class CommitComparisonService:
    """
    Utilities for determining whether a commit comparison needs to be recomputed
    (and enqueueing that recompute when necessary), and fetching associated comparisons
    for pulls
    """

    def __init__(self, commit_comparison: CommitComparison):
        self.commit_comparison = commit_comparison

    @cached_property
    def base_commit(self):
        if "base_commit" not in self.commit_comparison._state.fields_cache:
            # base_commit is already preloaded
            self.commit_comparison.base_commit = self._load_commit(
                self.commit_comparison.base_commit_id
            )
        return self.commit_comparison.base_commit

    @cached_property
    def compare_commit(self):
        if "compare_commit" not in self.commit_comparison._state.fields_cache:
            # compare_commit is already preloaded
            self.commit_comparison.compare_commit = self._load_commit(
                self.commit_comparison.compare_commit_id
            )
        return self.commit_comparison.compare_commit

    def needs_recompute(self) -> bool:
        if self._last_updated_before(self.compare_commit.updatestamp):
            return True

        if self._last_updated_before(self.base_commit.updatestamp):
            return True

        return False

    def _last_updated_before(self, timestamp: datetime) -> bool:
        """
        Returns true if the given timestamp occurred after the commit comparison's last update
        """
        timezone = pytz.utc
        if not timestamp:
            return False

        if timestamp.tzinfo is None:
            timestamp = timezone.localize(timestamp)
        else:
            timestamp = timezone.normalize(timestamp)

        return timezone.normalize(self.commit_comparison.updated_at) < timestamp

    def _load_commit(self, commit_id: int) -> Optional[Commit]:
        prefetch = Prefetch(
            "reports",
            queryset=CommitReport.objects.coverage_reports().filter(code=None),
        )
        return (
            Commit.objects.filter(pk=commit_id)
            .prefetch_related(prefetch)
            .defer("_report")
            .first()
        )

    @staticmethod
    def get_commit_comparison_for_pull(obj: Pull) -> Optional[CommitComparison]:
        comparison_qs = CommitComparison.objects.filter(
            base_commit__commitid=obj.compared_to,
            compare_commit__commitid=obj.head,
            base_commit__repository_id=obj.repository_id,
            compare_commit__repository_id=obj.repository_id,
        ).select_related("compare_commit", "base_commit")
        return comparison_qs.first()

    @classmethod
    def fetch_precomputed(self, repo_id: int, keys: List[Tuple]) -> QuerySet:
        comparison_table = CommitComparison._meta.db_table
        commit_table = Commit._meta.db_table
        queryset = CommitComparison.objects.raw(
            f"""
            select
                {comparison_table}.*,
                base_commit.commitid as base_commitid,
                compare_commit.commitid as compare_commitid
            from {comparison_table}
            inner join {commit_table} base_commit
                on base_commit.id = {comparison_table}.base_commit_id and base_commit.repoid = {repo_id}
            inner join {commit_table} compare_commit
                on compare_commit.id = {comparison_table}.compare_commit_id and compare_commit.repoid = {repo_id}
            where (base_commit.commitid, compare_commit.commitid) in %s
        """,
            [tuple(keys)],
        )

        # we need to make sure we're performing the query against the primary database
        # (and not the read replica) since we may have just inserted new comparisons
        # that we'd like to ensure are returned here
        return queryset.using("default")
