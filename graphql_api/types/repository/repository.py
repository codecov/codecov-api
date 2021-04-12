from ariadne import ObjectType

repository_bindable = ObjectType("Repository")

@repository_bindable.field("coverage")
def resolve_coverage(repo, info):
    if repo.cache:
        return repo.cache.get('commit', {}).get('totals', {}).get('c')

repository_bindable.set_alias("updatedAt", "updatestamp")
