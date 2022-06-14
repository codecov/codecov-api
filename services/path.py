import os.path
from dataclasses import dataclass
from typing import List, Union

from shared.reports.resources import Report

from graphql_api.types.enums import OrderingDirection, PathContentsFilters


@dataclass
class FilteredFilePath:
    """Class for keeping track of paths filtered by the path prefix."""

    full_path: str
    stripped_path: str


@dataclass
class TreeFile:
    """Class for keeping track of files in a path_tree"""

    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    full_path: str

    def __getitem__(self, item):
        return getattr(self, item)


@dataclass
class TreeDir:
    """Class for keeping track of directory in a path_tree"""

    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    children: list

    def __getitem__(self, item):
        return getattr(self, item)


@dataclass
class Dir:
    """Class for keeping track of an object containing files and directories"""

    kind: str
    name: str
    child_paths: list


def build_tree(
    report_files: list, path: str, filters: PathContentsFilters, commit_report: Report
) -> List[Union[TreeFile, TreeDir]]:
    tree = []
    search_value = filters.get(PathContentsFilters.SEARCH_VALUE.value)
    if search_value:
        tree = search_tree(
            files=report_files, search_value=search_value, commit_report=commit_report
        )
    else:
        tree = path_tree(files=report_files, path=path, commit_report=commit_report)

    print(tree)
    return apply_filters(tree=tree, filters=filters)


def apply_filters(
    tree: List[Union[TreeFile, TreeDir]], filters: PathContentsFilters
) -> List[Union[TreeFile, TreeDir]]:
    filter_parameter = filters.get(PathContentsFilters.ORDERING_PARAMETER.value)
    filter_direction = filters.get(PathContentsFilters.ORDERING_DIRECTION.value)
    if filter_parameter and filter_direction:
        parameter_value = filter_parameter.value
        direction_value = filter_direction.value
        # Used to cast the sorting type
        sorting_type = type(parameter_value)
        sorting_direction = (
            True if direction_value == OrderingDirection.DESC.value else False
        )
        tree = sorted(
            tree,
            key=lambda x: sorting_type(x[parameter_value]),
            reverse=sorting_direction,
        )

    return tree


def search_tree(
    files: list, search_value: str, commit_report: Report
) -> List[TreeFile]:
    filtered_paths_by_search = _filtered_paths_by_search(
        report_file_paths=files, search_value=search_value
    )
    return _build_search_tree(
        paths=filtered_paths_by_search, commit_report=commit_report
    )


def path_tree(
    files: list, path: str, commit_report: Report
) -> List[Union[TreeFile, TreeDir]]:
    filtered_files_by_path = _filter_files_by_path(
        report_file_paths=files, path_prefix=path
    )
    return _build_path_tree(paths=filtered_files_by_path, commit_report=commit_report)


def _build_path_tree(
    paths: List[FilteredFilePath], commit_report: Report
) -> List[Union[TreeFile, TreeDir]]:
    file_dir_tree = {}

    for path in paths:
        parts = path.stripped_path.split("/", 1)
        if len(parts) == 1:
            # Treated as a file
            name = parts[0]
            full_path = path.full_path
            totals = commit_report.get(full_path).totals
            file_dir_tree[name] = TreeFile(
                name=name,
                kind="file",
                hits=totals.hits,
                lines=totals.lines,
                coverage=totals.coverage,
                full_path=full_path,
            )
        else:
            # Treated as a directory
            dirname, remaining_path = parts
            if dirname not in file_dir_tree:
                file_dir_tree[dirname] = Dir(
                    kind="dir",
                    name=dirname,
                    child_paths=[],
                )
            filteredFilePath = FilteredFilePath(
                stripped_path=remaining_path, full_path=path.full_path
            )
            file_dir_tree[dirname].child_paths.append(filteredFilePath)

    res = []
    for item in file_dir_tree.values():
        if item.kind == "file":
            res.append(item)
        else:
            # recurse
            children = _build_path_tree(item.child_paths, commit_report)

            # sum up hits/lines from children
            hits, lines = (0, 0)

            for child in children:
                hits += child.hits
                lines += child.lines

            res.append(
                TreeDir(
                    kind=item.kind,
                    name=item.name,
                    hits=hits,
                    lines=lines,
                    coverage=float(hits / lines) * 100,
                    children=children,
                )
            )

    return res


def _build_search_tree(paths: List[str], commit_report: Report) -> List[TreeFile]:
    search_tree = []
    for path in paths:
        totals = commit_report.get(path).totals
        path_name = os.path.split(path)[1]
        search_tree.append(
            TreeFile(
                name=path_name,
                kind="file",
                hits=totals.hits,
                lines=totals.lines,
                coverage=float(totals.coverage),
                full_path=path,
            )
        )
    return search_tree


# Utils to filter paths by conditions
def _filter_files_by_path(
    report_file_paths: list, path_prefix: str
) -> List[FilteredFilePath]:
    filtered_files = []

    for path in report_file_paths:
        if path.startswith(path_prefix):
            filtered_files.append(
                FilteredFilePath(
                    full_path=path,
                    stripped_path=path
                    if not path_prefix
                    else path.replace(path_prefix + "/", "", 1),
                )
            )

    return filtered_files


def _filtered_paths_by_search(report_file_paths, search_value) -> List[str]:
    return [path for path in report_file_paths if search_value in path]
