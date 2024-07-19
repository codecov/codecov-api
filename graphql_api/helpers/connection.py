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


class DictCursorPaginator(CursorPaginator):
    """
    overrides CursorPaginator's position_from_instance method
    because it assumes that instance's fields are attributes on the
    instance. This doesn't work with the aggregate_test_results query
    because since it uses annotate() and values() the instance is actually
    a dict and the fields are keys in that dict.

    So if getattr fails to find the attribute on the instance then we try getting the "attr"
    via a dict access

    if the dict access fails then it throws an exception, although it would be a different
    """

    def position_from_instance(self, instance):
        position = []
        for order in self.ordering:
            parts = order.lstrip("-").split("__")
            attr = instance
            while parts:
                try:
                    attr = getattr(attr, parts[0])
                except AttributeError as attr_err:
                    try:
                        attr = attr[parts[0]]
                    except (KeyError, TypeError):
                        raise attr_err from None
                parts.pop(0)
            position.append(str(attr))
        return position


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
    paginator = DictCursorPaginator(queryset, ordering=ordering)
    page = paginator.page(first=first, after=after, last=last, before=before)

    return Connection(queryset, paginator, page)


@sync_to_async
def queryset_to_connection(*args, **kwargs):
    return queryset_to_connection_sync(*args, **kwargs)
