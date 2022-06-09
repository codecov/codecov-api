from typing import List

import yaml
from ariadne import ObjectType
from asgiref.sync import sync_to_async

from core.models import Commit
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from services.profiling import CriticalFile, ProfilingSummary

commit_bindable = ObjectType("Commit")

commit_bindable.set_alias("createdAt", "timestamp")
commit_bindable.set_alias("pullId", "pullid")
commit_bindable.set_alias("branchName", "branch")


@commit_bindable.field("coverageFile")
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
async def resolve_list_uploads(commit, info, **kwargs):
    command = info.context["executor"].get_command("commit")
    queryset = await command.get_uploads_of_commit(commit)
    return await queryset_to_connection(
        queryset, ordering=("id",), ordering_direction=OrderingDirection.ASC, **kwargs
    )


@commit_bindable.field("compareWithParent")
async def resolve_compare_with_parent(commit, info, **kwargs):
    parent_commit = None
    if commit.parent_commit_id:
        parent_commit = await CommitLoader.loader(info, commit.repository_id).load(
            commit.parent_commit_id
        )
    command = info.context["executor"].get_command("compare")
    return await command.compare_commits(commit, parent_commit)


@commit_bindable.field("flagNames")
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
