from dataclasses import dataclass
from shared.reports.resources import Report
from shared.reports.types import ReportFileSummary
from typing import List

@dataclass
class FilteredFilePath:
    """Class for keeping track of paths filtered by ."""
    full_path: str
    stripped_path: str

@dataclass
class TreeFile:
    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    full_path: str

@dataclass
class Dir:
    kind: str
    name: str
    child_paths: list

@dataclass
class TreeDir:
    kind: str
    name: str
    hits: int
    lines: int
    coverage: float
    children: list

def path_tree(paths: List[FilteredFilePath], commit_report: Report):
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
            children = path_tree(item.child_paths, commit_report)

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
                    coverage=(hits/lines)*100,
                    children=children,
                )
            )

    return res

def filter_files_by_path_prefix(
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