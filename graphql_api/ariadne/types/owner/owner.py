from ariadne import ObjectType
from cursor_pagination import CursorPaginator

from graphql_api.actions.repository import list_repository_for_owner

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner_bindable = ObjectType("Owner")


@owner_bindable.field("repositories")
def resolve_repositories(owner, info, first=None, after=None, last=None, before=None):
    current_user = info.context['request'].user
    queryset = list_repository_for_owner(current_user, owner)
    paginator = CursorPaginator(queryset, ordering=('-repoid',))
    if not first and not after:
        first = 100
    page = paginator.page(first=first, after=after, last=last, before=before)
    return {
        "edges": [
            {
                "cursor": paginator.cursor(page[pos]),
                "node": repository,
            } for pos, repository in enumerate(page)
        ],
        "totalCount": queryset.count(),
        "pageInfo": {
            "hasNextPage": page.has_next,
            "hasPreviousPage": page.has_previous,
            "startCursor": paginator.cursor(page[0]) if len(page) > 0 else None,
            "endCursor": paginator.cursor(page[-1]) if len(page) > 0 else None,
        }
    }
