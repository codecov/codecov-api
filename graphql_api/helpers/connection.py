import enum

from asgiref.sync import sync_to_async
from cursor_pagination import CursorPaginator

from graphql_api.types.enums import OrderingDirection


def build_connection_graphql(connection_name, type_node):
    edge_name = connection_name + "Edge"
    return f"""
        type {connection_name} {{
          edges: [{edge_name}]
          totalCount: Int!
          pageInfo: PageInfo!
        }}

        type {edge_name} {{
          cursor: String!
          node: {type_node}
        }}
    """


def field_order(field, ordering):
    if isinstance(field, enum.Enum):
        field = field.value
    if ordering == OrderingDirection.DESC:
        field = f"-{field}"
    return field


@sync_to_async
def queryset_to_connection(
    queryset,
    *,
    ordering,
    ordering_direction,
    first=None,
    after=None,
    last=None,
    before=None,
):
    """
    A method to take a queryset and return it in paginated order based on the cursor pattern.
    """
    if not first and not after:
        first = 100

    ordering = tuple(field_order(field, ordering_direction) for field in ordering)
    paginator = CursorPaginator(queryset, ordering=ordering)
    page = paginator.page(first=first, after=after, last=last, before=before)
    return {
        "edges": [
            {"cursor": paginator.cursor(page[pos]), "node": repository}
            for pos, repository in enumerate(page)
        ],
        "total_count": queryset.count(),
        "page_info": {
            "has_next_page": page.has_next,
            "has_previous_page": page.has_previous,
            "start_cursor": paginator.cursor(page[0]) if len(page) > 0 else None,
            "end_cursor": paginator.cursor(page[-1]) if len(page) > 0 else None,
        },
    }
