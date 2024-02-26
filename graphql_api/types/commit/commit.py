from typing import List

import sentry_sdk
import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case
from shared.reports.filtered import FilteredReportFile
from shared.reports.resources import ReportFile

import services.components as components_service
import services.path as path_service
import services.report as report_service
from codecov.db import sync_to_async
from core.models import Commit
from graphql_api.actions.commits import commit_uploads
from graphql_api.actions.comparison import validate_commit_comparison
from graphql_api.actions.path_contents import sort_path_contents
from graphql_api.dataloader.bundle_analysis import (
    load_bundle_analysis_comparison,
    load_bundle_analysis_report,
)
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import (
    queryset_to_connection,
    queryset_to_connection_sync,
)
from graphql_api.types.comparison.comparison import (
    MissingBaseCommit,
    MissingBaseReport,
    MissingHeadReport,
)
from graphql_api.types.enums import OrderingDirection, PathContentDisplayType
from graphql_api.types.errors import MissingCoverage, MissingHeadReport, UnknownPath
from graphql_api.types.errors.errors import UnknownFlags
from services.bundle_analysis import BundleAnalysisComparison, BundleAnalysisReport
from services.comparison import Comparison, ComparisonReport
from services.components import Component
from services.path import ReportPaths
from services.profiling import CriticalFile, ProfilingSummary
from services.report import ReadOnlyReport
from services.yaml import YamlStates, get_yaml_state

commit_bindable = ObjectType("Commit")

commit_bindable.set_alias("createdAt", "timestamp")
commit_bindable.set_alias("pullId", "pullid")
commit_bindable.set_alias("branchName", "branch")


@commit_bindable.field("coverageFile")
@sync_to_async
def resolve_file(commit, info, path, flags=None, components=None):
    _else, paths = None, []
    if components:
        all_components = components_service.commit_components(
            commit, info.context["request"].current_owner
        )
        filtered_components = components_service.filter_components_by_name(
            all_components, components
        )
        for fc in filtered_components:
            paths.extend(fc.paths)
        _else = FilteredReportFile(ReportFile(path), [])

    commit_report = commit.full_report.filter(flags=flags, paths=paths)
    file_report = commit_report.get(path, _else=_else)

    return {
        "commit_report": commit_report,
        "file_report": file_report,
        "commit": commit,
        "path": path,
        "flags": flags,
        "components": components,
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
async def resolve_yaml(commit: Commit, info) -> dict:
    command = info.context["executor"].get_command("commit")
    final_yaml = await command.get_final_yaml(commit)
    return yaml.dump(final_yaml)


@commit_bindable.field("yamlState")
@convert_kwargs_to_snake_case
async def resolve_yaml_state(commit: Commit, info) -> YamlStates:
    command = info.context["executor"].get_command("commit")
    final_yaml = await command.get_final_yaml(commit)
    return get_yaml_state(yaml=final_yaml)


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
async def resolve_compare_with_parent(commit: Commit, info, **kwargs):
    if not commit.parent_commit_id:
        return MissingBaseCommit()

    comparison_loader = ComparisonLoader.loader(info, commit.repository_id)
    commit_comparison = await comparison_loader.load(
        (commit.parent_commit_id, commit.commitid)
    )

    comparison_error = validate_commit_comparison(commit_comparison=commit_comparison)

    if comparison_error:
        return comparison_error

    if commit_comparison and commit_comparison.is_processed:

        current_owner = info.context["request"].current_owner
        parent_commit = await CommitLoader.loader(info, commit.repository_id).load(
            commit.parent_commit_id
        )
        comparison = Comparison(
            user=current_owner, base_commit=parent_commit, head_commit=commit
        )
        info.context["comparison"] = comparison

    if commit_comparison:
        return ComparisonReport(commit_comparison)


@commit_bindable.field("bundleAnalysisCompareWithParent")
@sync_to_async
def resolve_bundle_analysis_compare_with_parent(commit: Commit, info, **kwargs):
    base_commit = Commit.objects.filter(commitid=commit.parent_commit_id).first()
    if not base_commit:
        return MissingBaseCommit()

    bundle_analysis_comparison = load_bundle_analysis_comparison(base_commit, commit)

    # Store the created SQLite DB path in info.context
    # when the request is fully handled, have the file deleted
    if isinstance(bundle_analysis_comparison, BundleAnalysisComparison):
        info.context[
            "request"
        ].bundle_analysis_base_report_db_path = (
            bundle_analysis_comparison.comparison.base_report.db_path
        )
        info.context[
            "request"
        ].bundle_analysis_head_report_db_path = (
            bundle_analysis_comparison.comparison.head_report.db_path
        )

    return bundle_analysis_comparison


@commit_bindable.field("bundleAnalysisReport")
@sync_to_async
def resolve_bundle_analysis_report(
    commit: Commit, info, **kwargs
) -> BundleAnalysisReport:
    bundle_analysis_report = load_bundle_analysis_report(commit)

    # Store the created SQLite DB path in info.context
    # when the request is fully handled, have the file deleted
    if isinstance(bundle_analysis_report, BundleAnalysisReport):
        info.context[
            "request"
        ].bundle_analysis_head_report_db_path = bundle_analysis_report.report.db_path

    return bundle_analysis_report


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


@sentry_sdk.trace
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
    current_owner = info.context["request"].current_owner

    # TODO: Might need to add reports here filtered by flags in the future
    commit_report = report_service.build_report_from_commit(
        commit, report_class=ReadOnlyReport
    )
    if not commit_report:
        return MissingHeadReport()

    if filters is None:
        filters = {}
    search_value = filters.get("search_value")
    display_type = filters.get("display_type")

    flags_filter = filters.get("flags", [])
    component_filter = filters.get("components", [])

    component_paths = []
    component_flags = []

    if component_filter:
        all_components = components_service.commit_components(commit, current_owner)
        filtered_components = components_service.filter_components_by_name(
            all_components, component_filter
        )

        if not filtered_components:
            return MissingCoverage(
                f"missing coverage for report with components: {component_filter}"
            )

        for component in filtered_components:
            component_paths.extend(component.paths)
            if commit_report.flags:
                component_flags.extend(
                    component.get_matching_flags(commit_report.flags.keys())
                )

    if component_flags:
        if flags_filter:
            flags_filter = list(set(flags_filter) & set(component_flags))
        else:
            flags_filter = component_flags

    if flags_filter and not commit_report.flags:
        return UnknownFlags(f"No coverage with chosen flags: {flags_filter}")

    report_paths = ReportPaths(
        report=commit_report,
        path=path,
        search_term=search_value,
        filter_flags=flags_filter,
        filter_paths=component_paths,
    )

    if len(report_paths.paths) == 0:
        # we do not know about this path

        if path_service.provider_path_exists(path, commit, current_owner) is False:
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
def resolve_components(commit: Commit, info, filters=None) -> List[Component]:
    request = info.context["request"]
    info.context["component_commit"] = commit
    all_components = components_service.commit_components(commit, request.user)

    if filters and filters.get("components"):
        return components_service.filter_components_by_name(
            all_components, filters["components"]
        )

    return all_components
