from typing import List, Union

import yaml
from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async

import services.components as components
import services.path as path_service
from core.models import Commit
from graphql_api.actions.commits import commit_uploads
from graphql_api.actions.path_contents import sort_path_contents
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import (
    queryset_to_connection,
    queryset_to_connection_sync,
)
from graphql_api.types.enums import OrderingDirection, PathContentDisplayType
from graphql_api.types.errors import MissingCoverage, MissingHeadReport, UnknownPath
from services.archive import ReadOnlyReport, ReportService
from services.components import Component
from services.path import ReportPaths
from services.profiling import CriticalFile, ProfilingSummary

commit_bindable = ObjectType("Commit")

commit_bindable.set_alias("createdAt", "timestamp")
commit_bindable.set_alias("pullId", "pullid")
commit_bindable.set_alias("branchName", "branch")


@commit_bindable.field("coverageFile")
@sync_to_async
def resolve_file(commit, info, path, flags=None):
    commit_report = commit.full_report.filter(flags=flags)
    file_report = commit_report.get(path)

    return {
        "commit_report": commit_report,
        "file_report": file_report,
        "commit": commit,
        "path": path,
        "flags": flags,
    }


@commit_bindable.field("totals")
def resolve_totals(commit, info):
    command = info.context["executor"].get_command("commit")
    return command.fetch_totals(commit)


@commit_bindable.field("author")
def resolve_author(commit, info):
    if commit.author_id:
        return OwnerLoader.loader(info).load(commit.author_id)


@commit_bindable.field("parent")
def resolve_parent(commit, info):
    if commit.parent_commit_id:
        return CommitLoader.loader(info, commit.repository_id).load(
            commit.parent_commit_id
        )


@commit_bindable.field("yaml")
async def resolve_yaml(commit, info):
    command = info.context["executor"].get_command("commit")
    final_yaml = await command.get_final_yaml(commit)
    return yaml.dump(final_yaml)


@commit_bindable.field("uploads")
@sync_to_async
def resolve_list_uploads(commit: Commit, info, **kwargs):
    queryset = commit_uploads(commit)

    if not kwargs:  # temp to override kwargs -> return all current uploads
        kwargs["first"] = queryset.count()

    return queryset_to_connection_sync(
        queryset, ordering=("id",), ordering_direction=OrderingDirection.ASC, **kwargs
    )


@commit_bindable.field("compareWithParent")
def resolve_compare_with_parent(commit, info, **kwargs):
    if not commit.parent_commit_id:
        return None

    comparison_loader = ComparisonLoader.loader(info, commit.repository_id)
    return comparison_loader.load((commit.parent_commit_id, commit.commitid))


@commit_bindable.field("flagNames")
@sync_to_async
def resolve_flags(commit, info, **kwargs):
    return commit.full_report.flags.keys()


@commit_bindable.field("criticalFiles")
@sync_to_async
def resolve_critical_files(commit: Commit, info, **kwargs) -> List[CriticalFile]:
    """
    The critical files for this particular commit (might be empty
    depending on whether the profiling info included a commit SHA).
    The results of this resolver could be different than that of the
    `repository.criticalFiles` resolver.
    """
    profiling_summary = ProfilingSummary(commit.repository, commit_sha=commit.commitid)
    return profiling_summary.critical_files


@commit_bindable.field("pathContents")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_path_contents(commit: Commit, info, path: str = None, filters=None):
    """
    The file directory tree is a list of all the files and directories
    extracted from the commit report of the latest, head commit.
    The is resolver results in a list that represent the tree with files
    and nested directories.
    """
    user = info.context["request"].user

    # TODO: Might need to add reports here filtered by flags in the future
    commit_report = ReportService().build_report_from_commit(
        commit, report_class=ReadOnlyReport
    )
    if not commit_report:
        return MissingHeadReport()

    if filters is None:
        filters = {}
    search_value = filters.get("search_value")
    display_type = filters.get("display_type")

    report_paths = ReportPaths(
        report=commit_report,
        path=path,
        search_term=search_value,
    )

    if len(report_paths.paths) == 0:
        # we do not know about this path

        if path_service.provider_path_exists(path, commit, user) is False:
            # file doesn't exist
            return UnknownPath(f"path does not exist: {path}")

        # we're just missing coverage for the file
        return MissingCoverage(f"missing coverage for path: {path}")

    if search_value or display_type == PathContentDisplayType.LIST:
        items = report_paths.full_filelist()
    else:
        items = report_paths.single_directory()
    return {"results": sort_path_contents(items, filters)}


@commit_bindable.field("errors")
async def resolve_errors(commit, info, errorType):
    command = info.context["executor"].get_command("commit")
    queryset = await command.get_commit_errors(commit, error_type=errorType)
    return await queryset_to_connection(
        queryset,
        ordering=("updated_at",),
        ordering_direction=OrderingDirection.ASC,
    )


@commit_bindable.field("totalUploads")
async def resolve_total_uploads(commit, info):
    command = info.context["executor"].get_command("commit")
    return await command.get_uploads_number(commit)


@commit_bindable.field("components")
@sync_to_async
def resolve_components(commit: Commit, info) -> List[Component]:
    request = info.context["request"]
    info.context["component_commit"] = commit
    return components.commit_components(commit, request.user)
