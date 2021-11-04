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


def _build_paginator_ordering(primary_ordering, ordering_direction, unique_ordering):
    primary_ordering_value = (
        primary_ordering.value
        if isinstance(primary_ordering, enum.Enum)
        else primary_ordering
    )

    primary_ordering_with_direction = (
        f"-{primary_ordering_value}"
        if ordering_direction == OrderingDirection.DESC
        else primary_ordering_value
    )
    unique_ordering_with_direction = (
        f"-{unique_ordering}"
        if ordering_direction == OrderingDirection.DESC
        else unique_ordering
    )

    return (
        primary_ordering_with_direction,
        unique_ordering_with_direction,
    )


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

    paginator_ordering = _build_paginator_ordering(
        ordering, ordering_direction, queryset.model._meta.pk.name
    )
    paginator = CursorPaginator(queryset, ordering=paginator_ordering)
    page = paginator.page(first=first, after=after, last=last, before=before)
    return {
        "edges": [
            {"cursor": paginator.cursor(page[pos]), "node": repository,}
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
