import asyncio

import yaml
from ariadne import ObjectType

from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.commit_comparison import CommitComparisonLoader
from graphql_api.dataloader.commit_report import CommitReportLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection

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
async def resolve_totals(commit, info):
    commit_report = await CommitReportLoader.loader(info).load(commit.id)
    if commit_report:
        return commit_report.reportleveltotals


@commit_bindable.field("author")
def resolve_author(commit, info):
    if commit.author_id:
        return OwnerLoader.loader(info).load(commit.author_id)


@commit_bindable.field("parent")
def resolve_parent(commit, info):
    if commit.parent_commit_id is not None:
        return CommitLoader.loader(info, commit.repository.repoid).load(
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
        queryset, ordering="id", ordering_direction=OrderingDirection.ASC, **kwargs
    )


@commit_bindable.field("compareWithParent")
async def resolve_compare_with_parent(commit, info, **kwargs):
    parent_commit = None
    comparison = None
    if commit.parent_commit_id is not None:
        parent_commit, comparison = await asyncio.gather(
            CommitLoader.loader(info, commit.repository.repoid).load(
                commit.parent_commit_id
            ),
            CommitComparisonLoader.loader(info).load(
                (commit.parent_commit_id, commit.commitid)
            ),
        )

    # TODO: we may be able to return the comparison here if found.
    # still calling the command below to handle `needs_recalculation`
    # (maybe move that logic into the model and call it here)

    command = info.context["executor"].get_command("compare")
    return await command.compare_commit_with_parent(
        commit, parent_commit=parent_commit, comparison=comparison
    )


@commit_bindable.field("flagNames")
def resolve_flags(commit, info, **kwargs):
    return commit.full_report.flags.keys()
