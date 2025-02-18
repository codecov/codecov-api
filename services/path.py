from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Iterable

import sentry_sdk
from asgiref.sync import async_to_sync
from django.conf import settings
from shared.reports.resources import Report
from shared.reports.types import ReportTotals
from shared.torngit.exceptions import TorngitClientError
from shared.utils.match import Matcher

import services.report as report_service
from codecov_auth.models import Owner
from core.models import Commit
from services.repo_providers import RepoProviderService


class PathNode:
    """
    Generic node in a file/directory tree that has coverage totals.
    Expects a `totals: ReportTotals` attribute to be set.
    """

    @property
    def name(self) -> str:
        return self.full_path.split("/")[-1]

    @property
    def lines(self) -> int:
        return self.totals.lines or 0

    @property
    def hits(self) -> int:
        return self.totals.hits or 0

    @property
    def partials(self) -> int:
        return self.totals.partials or 0

    @property
    def misses(self) -> int:
        return self.totals.misses or 0

    @property
    def coverage(self) -> float:
        if self.lines > 0:
            return float(self.hits / self.lines) * 100
        else:
            return 0.0


@dataclass
class File(PathNode):
    """
    File node in a file/directory tree.
    """

    full_path: str
    totals: ReportTotals


@dataclass
class Dir(PathNode):
    """
    Directory node in a file/directory tree.
    """

    full_path: str
    children: list[File | Dir]

    @cached_property
    def totals(self) -> ReportTotals:
        # A dir's totals are sum of its children's totals
        totals = ReportTotals.default_totals()
        for child in self.children:
            totals.lines += child.lines
            totals.hits += child.hits
            totals.partials += child.partials
            totals.misses += child.misses
        return totals


@dataclass
class PrefixedPath:
    full_path: str
    prefix: str

    @property
    def relative_path(self) -> str:
        """
        The path relative to the `prefix`.  For example, if `full_path`
        is `a/b/c/d.txt` and `prefix` is `a/b` then this method would return `c/d.txt`.
        """
        if not self.prefix:
            return self.full_path
        else:
            return self.full_path.removeprefix(f"{self.prefix}/")

    @property
    def is_file(self) -> bool:
        parts = self.relative_path.split("/")
        return len(parts) == 1

    @property
    def basename(self) -> str:
        """
        The base path name (including the prefix).  For example, if `full_path`
        is `a/b/c/d.txt` and `prefix` is `a/b` then this method would return `a/b/c`.
        """
        name = self.relative_path.split("/", 1)[0]
        if self.prefix:
            return f"{self.prefix}/{name}"
        else:
            return name


def is_subpath(full_path: str, subpath: str) -> bool:
    if not subpath:
        return True
    return full_path.startswith(f"{subpath}/") or full_path == subpath


def dashboard_commit_file_url(
    path: str | None,
    service: str,
    owner: str,
    repo: str,
    commit: Commit,
) -> str:
    if path is None:
        path = ""
    report = commit.full_report
    is_file = report and path in report.files
    commit_path = f"blob/{path}" if is_file else f"tree/{path}"
    return f"{settings.CODECOV_DASHBOARD_URL}/{service}/{owner}/{repo}/commit/{commit.commitid}/{commit_path}"


class ReportPaths:
    """
    Contains methods for getting path information out of a single report.
    """

    @sentry_sdk.trace
    def __init__(
        self,
        report: Report,
        path: str | None = None,
        search_term: str | None = None,
        filter_flags: list[str] = [],
        filter_paths: list[str] = [],
    ):
        self.report = report
        self.unfiltered_report = report
        self.filter_flags = filter_flags
        self.filter_paths = filter_paths
        self.prefix = path or ""

        # Filter report if flags or paths exist
        if self.filter_flags or self.filter_paths:
            self.report = self.report.filter(
                paths=self.filter_paths, flags=self.filter_flags
            )

        self._paths = [
            PrefixedPath(full_path=full_path, prefix=self.prefix)
            for full_path in self.files
            if is_subpath(full_path, self.prefix)
        ]

        if search_term:
            self._paths = [
                path
                for path in self.paths
                if search_term.lower() in path.relative_path.lower()
            ]

    @cached_property
    def files(self) -> list[str]:
        # No filtering, just return files in Report
        if not self.filter_flags and not self.filter_paths:
            return self.report.files

        files = []
        # Do flag filtering if needed
        if self.filter_flags:
            files = report_service.files_belonging_to_flags(
                commit_report=self.unfiltered_report, flags=self.filter_flags
            )
        else:
            files = [file.name for file in self.unfiltered_report]

        # Do path filtering if needed
        if self.filter_paths:
            matcher = Matcher(self.filter_paths)
            files = [file for file in files if matcher.match(file)]

        return files

    def _filter_commit_report(self) -> None:
        self.report = self.report.filter(flags=self.filter_flags)

    @property
    def paths(self) -> list[PrefixedPath]:
        return self._paths

    @sentry_sdk.trace
    def full_filelist(self) -> list[File | Dir]:
        """
        Return a flat file list of all files under the specified `path` prefix/directory.
        """
        return [
            File(full_path=path.full_path, totals=self._totals(path))
            for path in self.paths
        ]

    @sentry_sdk.trace
    def single_directory(self) -> list[File | Dir]:
        """
        Return a single directory (specified by `path`) of mixed file/directory results.
        """
        return self._single_directory_recursive(self.paths)

    def _totals(self, path: PrefixedPath) -> ReportTotals:
        """
        Returns the report totals for a given prefixed path.
        """
        # Fixes an issue when filtering by flags does not work in the case where
        # one flag covers half of the file and another flag covers another half.
        # Using get_file_totals will return the totals for coverage of all flags
        # applied to the file instead of just the filter flags being queried
        if self.filter_flags:
            return self.report.get(path.full_path).totals
        else:
            return self.report.get_file_totals(path.full_path)

    def _single_directory_recursive(
        self, paths: Iterable[PrefixedPath]
    ) -> list[File | Dir]:
        grouped = defaultdict(list)
        for path in paths:
            grouped[path.basename].append(path)

        results: list[File | Dir] = []

        for basename, paths in grouped.items():
            if len(paths) == 1 and paths[0].is_file:
                path = paths[0]
                results.append(
                    File(full_path=path.full_path, totals=self._totals(path))
                )
            else:
                children = self._single_directory_recursive(
                    PrefixedPath(full_path=path.full_path, prefix=basename)
                    for path in paths
                )
                results.append(Dir(full_path=basename, children=children))

        return results


def provider_path_exists(path: str, commit: Commit, owner: Owner) -> bool | None:
    """
    Check whether the given path exists on the provider.
    """
    try:
        adapter = RepoProviderService().get_adapter(owner, commit.repository)
        async_to_sync(adapter.list_files)(commit.commitid, path)
        return True
    except TorngitClientError as e:
        if e.code == 404:
            return False
        else:
            # more generic error from provider
            return None
