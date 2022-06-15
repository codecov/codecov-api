import enum
import os.path
from dataclasses import dataclass
from typing import List, Union

from shared.reports.resources import Report


@dataclass
class FilteredFilePath:
    """Class for keeping track of paths filtered by the path prefix."""

    full_path: str
    stripped_path: str


@dataclass
class File:
    """Class for keeping track of files in a list of paths"""

    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    full_path: str


@dataclass
class Dir:
    """Class for keeping track of directory in a list of paths"""

    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    children: list


@dataclass
class Group:
    """Class for keeping track of an object containing files and directories"""

    kind: str
    name: str
    child_paths: list


def path_contents(
    report_files: list, path: str, filters, commit_report: Report
) -> List[Union[File, Dir]]:
    tree = []
    search_value = filters.get("searchValue")
    if search_value:
        tree = search_list(
            files=report_files, search_value=search_value, commit_report=commit_report
        )
    else:
        tree = path_list(files=report_files, path=path, commit_report=commit_report)
    return apply_filters(tree=tree, filters=filters)


def apply_filters(tree: List[Union[File, Dir]], filters) -> List[Union[File, Dir]]:
    filter_parameter = filters.get("ordering", {}).get("parameter")
    filter_direction = filters.get("ordering", {}).get("direction")
    if filter_parameter and filter_direction:
        parameter_value = filter_parameter.value
        direction_value = filter_direction.value
        is_reverse = True if direction_value == "descending" else False
        tree = sorted(
            tree,
            key=lambda x: getattr(x, parameter_value),
            reverse=is_reverse,
        )

    return tree


def search_list(files: list, search_value: str, commit_report: Report) -> List[File]:
    filtered_paths_by_search = _filtered_files_by_search(
        report_file_paths=files, search_value=search_value
    )
    return _build_search_list(
        paths=filtered_paths_by_search, commit_report=commit_report
    )


def path_list(files: list, path: str, commit_report: Report) -> List[Union[File, Dir]]:
    filtered_files_by_path = _filter_files_by_path(
        report_file_paths=files, path_prefix=path
    )
    return _build_path_list(paths=filtered_files_by_path, commit_report=commit_report)


def _build_path_list(
    paths: List[FilteredFilePath], commit_report: Report
) -> List[Union[File, Dir]]:
    file_dir_tree = {}

    for path in paths:
        parts = path.stripped_path.split("/", 1)
        if len(parts) == 1:
            # Treated as a file
            name = parts[0]
            full_path = path.full_path
            totals = commit_report.get(full_path).totals
            file_dir_tree[name] = File(
                name=name,
                kind="file",
                hits=totals.hits,
                lines=totals.lines,
                coverage=float(totals.coverage),
                full_path=full_path,
            )
        else:
            # Treated as a directory
            dirname, remaining_path = parts
            if dirname not in file_dir_tree:
                file_dir_tree[dirname] = Group(
                    kind="dir",
                    name=dirname,
                    child_paths=[],
                )
            filteredFilePath = FilteredFilePath(
                stripped_path=remaining_path, full_path=path.full_path
            )
            file_dir_tree[dirname].child_paths.append(filteredFilePath)

    file_dir_list = []
    for item in file_dir_tree.values():
        if item.kind == "file":
            file_dir_list.append(item)
        else:
            # recurse
            children = _build_path_list(item.child_paths, commit_report)

            # sum up hits/lines from children
            hits, lines = (0, 0)

            for child in children:
                hits += child.hits
                lines += child.lines

            file_dir_list.append(
                Dir(
                    kind=item.kind,
                    name=item.name,
                    hits=hits,
                    lines=lines,
                    coverage=float(hits / lines) * 100,
                    children=children,
                )
            )

    return file_dir_list


def _build_search_list(paths: List[str], commit_report: Report) -> List[File]:
    search_list = []
    for path in paths:
        totals = commit_report.get(path).totals
        path_name = os.path.split(path)[1]
        search_list.append(
            File(
                name=path_name,
                kind="file",
                hits=totals.hits,
                lines=totals.lines,
                coverage=float(totals.coverage),
                full_path=path,
            )
        )
    return search_list


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


def _filtered_files_by_search(report_file_paths, search_value) -> List[str]:
    return [path for path in report_file_paths if search_value in path]
