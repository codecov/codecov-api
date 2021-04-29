from ariadne import ObjectType

from graphql_api.dataloader.owner import load_owner_by_id


repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")


@repository_bindable.field("coverage")
def resolve_coverage(repo, info):
    if repo.cache:
        return repo.cache.get("commit", {}).get("totals", {}).get("c")


@repository_bindable.field("author")
def resolve_author(repository, info):
    return load_owner_by_id(info, repository.author_id)
