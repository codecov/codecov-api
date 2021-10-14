from ariadne import ObjectType
from graphql_api.types.enums import OrderingDirection
from graphql_api.helpers.connection import queryset_to_connection

from graphql_api.dataloader.owner import load_owner_by_id


repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")

# latest_commit_at and coverage have their NULL value defaulted to -1/an old date
# so the NULL would end up last in the queryset as we do not have control over
# the order_by call. The true value of is under true_*; which would actually contain NULL
# see with_cache_latest_commit_at()/with_cache_coverage() from core/managers.py
repository_bindable.set_alias("latestCommitAt", "true_latest_commit_at")
repository_bindable.set_alias("coverage", "true_coverage")


@repository_bindable.field("branch")
def resolve_branch(repository, info, name):
    command = info.context["executor"].get_command("branch")
    return command.fetch_branch(repository, name)


@repository_bindable.field("author")
def resolve_author(repository, info):
    return load_owner_by_id(info, repository.author_id)


@repository_bindable.field("commit")
def resolve_commit(repository, info, id):
    command = info.context["executor"].get_command("commit")
    return command.fetch_commit(repository, id)


@repository_bindable.field("uploadToken")
def resolve_upload_token(repository, info):
    command = info.context["executor"].get_command("repository")
    return command.get_upload_token(repository)


@repository_bindable.field("pulls")
async def resolve_pulls(repository, info, **kwargs):
    command = info.context["executor"].get_command("pull")
    queryset = await command.fetch_pull_requests(repository)
    return await queryset_to_connection(
        queryset, ordering="id", ordering_direction=OrderingDirection.ASC, **kwargs
    )
