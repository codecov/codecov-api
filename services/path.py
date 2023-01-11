from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Iterable, List, Union

from asgiref.sync import async_to_sync
from shared.reports.resources import Report
from shared.reports.types import ReportTotals
from shared.torngit.exceptions import TorngitClientError

from codecov_auth.models import Owner
from core.models import Commit
from services.repo_providers import RepoProviderService


class PathNode:
    """
    Generic node in a file/directory tree that has coverage totals.
    Expects a `totals: ReportTotals` attribute to be set.
    """

    @property
    def name(self):
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
    children: List[PathNode]

    @cached_property
    def totals(self):
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
    def relative_path(self):
        """
        The path relative to the `prefix`.  For example, if `full_path`
        is `a/b/c/d.txt` and `prefix` is `a/b` then this method would return `c/d.txt`.
        """
        if not self.prefix:
            return self.full_path
        else:
            return self.full_path.replace(f"{self.prefix}/", "", 1)

    @property
    def is_file(self):
        parts = self.relative_path.split("/")
        return len(parts) == 1

    @property
    def basename(self):
        """
        The base path name (including the prefix).  For example, if `full_path`
        is `a/b/c/d.txt` and `prefix` is `a/b` then this method would return `a/b/c`.
        """
        name = self.relative_path.split("/", 1)[0]
        if self.prefix:
            return f"{self.prefix}/{name}"
        else:
            return name


def is_subpath(full_path: str, subpath: str):
    if not subpath:
        return True
    return full_path.startswith(f"{subpath}/") or full_path == subpath


class ReportPaths:
    """
    Contains methods for getting path information out of a single report.
    """

    def __init__(
        self, report: Report, path: PrefixedPath = None, search_term: str = None
    ):
        self.report = report
        self.prefix = path or ""

        self._paths = [
            PrefixedPath(full_path=full_path, prefix=self.prefix)
            for full_path in report.files
            if is_subpath(full_path, self.prefix)
        ]

        if search_term:
            self._paths = [
                path for path in self.paths if search_term in path.relative_path
            ]

    @property
    def paths(self):
        return self._paths

    def full_filelist(self) -> Iterable[File]:
        """
        Return a flat file list of all files under the specified `path` prefix/directory.
        """
        return [
            File(full_path=path.full_path, totals=self._totals(path))
            for path in self.paths
        ]

    def single_directory(self) -> Iterable[Union[File, Dir]]:
        """
        Return a single directory (specified by `path`) of mixed file/directory results.
        """
        return self._single_directory_recursive(self.paths)

    def _totals(self, path: PrefixedPath) -> ReportTotals:
        """
        Returns the report totals for a given prefixed path.
        """
        return self.report.get(path.full_path).totals

    def _single_directory_recursive(
        self, paths: Iterable[PrefixedPath]
    ) -> Iterable[Union[File, Dir]]:
        grouped = defaultdict(list)
        for path in paths:
            grouped[path.basename].append(path)

        results = []

        for basename, paths in grouped.items():
            paths = list(paths)
            if len(paths) == 1 and paths[0].is_file:
                path = paths[0]
                results.append(
                    File(full_path=path.full_path, totals=self._totals(path))
                )
            else:
                children = self._single_directory_recursive(
                    [
                        PrefixedPath(full_path=path.full_path, prefix=basename)
                        for path in paths
                    ]
                )
                results.append(Dir(full_path=basename, children=children))

        return results


def provider_path_exists(path: str, commit: Commit, user: Owner):
    """
    Check whether the given path exists on the provider.
    """
    try:
        adapter = RepoProviderService().get_adapter(user, commit.repository)
        async_to_sync(adapter.list_files)(commit.commitid, path)
        return True
    except TorngitClientError as e:
        if e.code == 404:
            return False
        else:
            # more generic error from provider
            return None
