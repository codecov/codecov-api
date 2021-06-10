from ariadne import ObjectType

from graphql_api.dataloader.owner import load_owner_by_id


repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")
repository_bindable.set_alias("latestCommitAt", "latest_commit_at")


@repository_bindable.field("author")
def resolve_author(repository, info):
    return load_owner_by_id(info, repository.author_id)


@repository_bindable.field("commit")
def resolve_commit(repository, info, id):
    command = info.context["executor"].get_command("commit")
    return command.fetch_commit(repository, id)
