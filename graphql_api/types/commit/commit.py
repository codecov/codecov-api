import yaml
from ariadne import ObjectType
from asgiref.sync import sync_to_async

from graphql_api.dataloader.owner import load_owner_by_id
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection

commit_bindable = ObjectType("Commit")

commit_bindable.set_alias("createdAt", "timestamp")
commit_bindable.set_alias("pullId", "pullid")
commit_bindable.set_alias("branchName", "branch")


@commit_bindable.field("totals")
def resolve_totals(commit, info):
    if commit.commitreport:
        return commit.commitreport.reportleveltotals


@commit_bindable.field("author")
def resolve_author(commit, info):
    if commit.author_id:
        return load_owner_by_id(info, commit.author_id)


@commit_bindable.field("parent")
def resolve_parent(commit, info):
    command = info.context["executor"].get_command("commit")
    return command.fetch_commit(commit.repository, commit.parent_commit_id)


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
