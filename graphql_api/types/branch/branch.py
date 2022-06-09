import string
from ariadne import ObjectType
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

    filtered_file_paths = _get_files_filtered_by_path(report_files, path)
    file_tree = traverse(filtered_file_paths, commit_report)

    return file_tree

def traverse(paths, commit_report):
    grouped = {}

    for path in paths:
        parts = path.get("changing_name").split("/", 1)
        if len(parts) == 1:
            # Treated as a file
            name = parts[0]
            file_path = path.get("file_path")
            totals = commit_report.get(file_path).totals
            grouped[name] = {
                "type": "file",
                "name": name,
                "hits": totals.hits,
                "lines": totals.lines,
                "coverage": totals.coverage,
                "file_path": file_path,
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
            path_obj = {"changing_name": remaining_path, "file_path": path.get("file_path")}
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

            res.append({
                "type": item["type"],
                "name": item["name"],
                "hits": hits,
                "lines": lines,
                "coverage": (hits/lines)*100,
                "children": children,
            })

    return res



def _get_files_filtered_by_path(report_files, path):
    filtered_files = []

    for _file in report_files:
        if _file.startswith(path) :
            filtered_files.append({
                "file_path": _file,
                "changing_name": _file if not path else _file.replace(path + '/', '', 1)
            })

    return filtered_files