from ariadne import ObjectType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async

from core.models import Repository
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from services.profiling import CriticalFiles

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
    return OwnerLoader.loader(info).load(repository.author_id)


@repository_bindable.field("commit")
def resolve_commit(repository, info, id):
    command = info.context["executor"].get_command("commit")
    return command.fetch_commit(repository, id)


@repository_bindable.field("uploadToken")
def resolve_upload_token(repository, info):
    command = info.context["executor"].get_command("repository")
    return command.get_upload_token(repository)


@repository_bindable.field("pull")
def resolve_pull(repository, info, id):
    command = info.context["executor"].get_command("pull")
    return command.fetch_pull_request(repository, id)


@repository_bindable.field("pulls")
@convert_kwargs_to_snake_case
async def resolve_pulls(
    repository, info, filters=None, ordering_direction=OrderingDirection.DESC, **kwargs
):
    command = info.context["executor"].get_command("pull")
    queryset = await command.fetch_pull_requests(repository, filters)
    return await queryset_to_connection(
        queryset,
        ordering="pullid",
        ordering_direction=ordering_direction,
        ordering_unique=True,
        **kwargs,
    )


@repository_bindable.field("commits")
@convert_kwargs_to_snake_case
async def resolve_commits(repository, info, filters=None, **kwargs):
    command = info.context["executor"].get_command("commit")
    queryset = await command.fetch_commits(repository, filters)
    res = await queryset_to_connection(
        queryset,
        ordering="timestamp",
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )

    for edge in res["edges"]:
        commit = edge["node"]
        # cache all resulting commits in dataloader
        loader = CommitLoader.loader(info, repository.repoid)
        loader.cache(commit)

    return res


@repository_bindable.field("branches")
@convert_kwargs_to_snake_case
async def resolve_branches(repository, info, **kwargs):
    command = info.context["executor"].get_command("branch")
    queryset = await command.fetch_branches(repository)
    return await queryset_to_connection(
        queryset,
        ordering="updatestamp",
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@repository_bindable.field("defaultBranch")
def resolve_default_branch(repository, info):
    return repository.branch


@repository_bindable.field("criticalFiles")
@sync_to_async
def resolve_critical_files(repository: Repository, info):
    """
    The current critical files for this repository - not tied to any
    particular commit or branch.  Based on the most recently received
    profiling data.

    See the `commit.criticalFiles` resolver for commit-specific files.
    """
    critical_files = CriticalFiles(repository)
    return [{"name": filename} for filename in critical_files.filenames]
