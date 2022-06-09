import string
from dataclasses import dataclass
from typing import List

from ariadne import ObjectType
from shared.reports.resources import Report
from shared.reports.types import ReportFileSummary

from core.models import Branch

branch_bindable = ObjectType("Branch")


@branch_bindable.field("head")
def resolve_head_commit(branch, info):
    command = info.context["executor"].get_command("commit")
    return command.fetch_commit(branch.repository, branch.head)


@branch_bindable.field("files")
async def resolve_files(branch: Branch, info, path: string):
    command = info.context["executor"].get_command("commit")
    head_commit = await command.fetch_commit(branch.repository, branch.head)

    # TODO: Might need to add reports here filtered by flags in the future
    commit_report = head_commit.full_report
    report_files = commit_report.files

    filtered_file_paths = filter_files_by_url_path(report_files, path)
    file_tree = traverse(filtered_file_paths, commit_report)

    return file_tree


@dataclass
class FilteredFilePath:
    """Class for keeping track of paths filtered by ."""

    full_path: str
    stripped_path: str

    def __init__(self, full_path: str, stripped_path: str):
        self.full_path = full_path
        self.stripped_path = stripped_path


def traverse(paths: List[FilteredFilePath], commit_report: Report):
    grouped = {}

    for path in paths:
        parts = path.stripped_path.split("/", 1)
        if len(parts) == 1:
            # Treated as a file
            name = parts[0]
            full_path = path.full_path
            totals = commit_report.get(full_path).totals
            grouped[name] = {
                "type": "file",
                "name": name,
                "hits": totals.hits,
                "lines": totals.lines,
                "coverage": totals.coverage,
                "full_path": full_path,
            }
        else:
            # Treated as a directory
            dirname, remaining_path = parts
            if dirname not in grouped:
                grouped[dirname] = {
                    "type": "dir",
                    "name": dirname,
                    "child_paths": [],
                }
            path_obj = FilteredFilePath(
                stripped_path=remaining_path, full_path=path.full_path
            )
            grouped[dirname]["child_paths"].append(path_obj)

    res = []
    for item in grouped.values():
        if item["type"] == "file":
            res.append(item)
        else:
            # recurse
            children = traverse(item["child_paths"], commit_report)

            # sum up hits/lines from children
            hits, lines = (0, 0)

            for child in children:
                hits += child["hits"]
                lines += child["lines"]

            res.append(
                {
                    "type": item["type"],
                    "name": item["name"],
                    "hits": hits,
                    "lines": lines,
                    "coverage": (hits / lines) * 100,
                    "children": children,
                }
            )

    return res


def filter_files_by_url_path(
    report_file_paths: List[ReportFileSummary], url_path: str
) -> List[FilteredFilePath]:
    filtered_files = []

    for path in report_file_paths:
        if path.startswith(url_path):
            filtered_files.append(
                FilteredFilePath(
                    full_path=path,
                    stripped_path=path
                    if not url_path
                    else path.replace(url_path + "/", "", 1),
                )
            )

    return filtered_files
