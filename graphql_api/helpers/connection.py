import enum
from dataclasses import dataclass
from functools import cached_property

from cursor_pagination import CursorPage, CursorPaginator
from django.db.models import QuerySet

from codecov.db import sync_to_async
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


@dataclass
class Connection:
    queryset: QuerySet
    paginator: CursorPaginator
    page: CursorPage

    @cached_property
    def edges(self):
        return [
            {"cursor": self.paginator.cursor(self.page[pos]), "node": node}
            for pos, node in enumerate(self.page)
        ]

    @sync_to_async
    def total_count(self, *args, **kwargs):
        return self.queryset.count()

    @cached_property
    def start_cursor(self):
        return self.paginator.cursor(self.page[0]) if len(self.page) > 0 else None

    @cached_property
    def end_cursor(self):
        return self.paginator.cursor(self.page[-1]) if len(self.page) > 0 else None

    @sync_to_async
    def page_info(self, *args, **kwargs):
        return {
            "has_next_page": self.page.has_next,
            "has_previous_page": self.page.has_previous,
            "start_cursor": self.start_cursor,
            "end_cursor": self.end_cursor,
        }


def queryset_to_connection_sync(
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
    if not first and not last:
        first = 25

    ordering = tuple(field_order(field, ordering_direction) for field in ordering)
    paginator = CursorPaginator(queryset, ordering=ordering)
    page = paginator.page(first=first, after=after, last=last, before=before)
    return Connection(queryset, paginator, page)


@sync_to_async
def queryset_to_connection(*args, **kwargs):
    return queryset_to_connection_sync(*args, **kwargs)
