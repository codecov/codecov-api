from ariadne import ObjectType

repository_bindable = ObjectType("Repository")

@repository_bindable.field("coverage")
def resolve_coverage(repo, info):
    try:
        return repo.cache['commit']['totals']['c']
    except:
        # No coverage in the cache
        return None
