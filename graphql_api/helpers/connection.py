import enum
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Dict, List, Optional

from cursor_pagination import CursorPage, CursorPaginator
from django.db.models import QuerySet

from codecov.commands.exceptions import ValidationError
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


class ArrayPaginator:
    """Cursor-based paginator for in-memory arrays."""

    def __init__(
        self,
        data: List[Any],
        first: Optional[int] = None,
        last: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ):
        self.data = data
        self.start_index = 0
        self.end_index = len(data)

        if first and last:
            raise ValidationError("Cannot provide both 'first' and 'last'")

        if after is not None:
            try:
                self.start_index = int(after) + 1
            except ValueError:
                raise ValidationError("'after' cursor must be an integer")

        if before is not None:
            try:
                self.end_index = min(self.end_index, int(before))
            except ValueError:
                raise ValidationError("'before' cursor must be an integer")

        # Ensure valid bounds after 'after' and 'before'
        self.start_index = max(self.start_index, 0)
        self.end_index = min(self.end_index, len(data))

        if first is not None:
            self.end_index = min(self.start_index + first, len(data))

        if last is not None:
            range_length = self.end_index - self.start_index
            if range_length > last:
                self.start_index = self.end_index - last

        # Ensure bounds remain valid
        self.start_index = max(self.start_index, 0)
        self.end_index = min(self.end_index, len(data))

    def cursor(self, position: int) -> str:
        """Generate a cursor based on the position (index)."""
        return str(position)

    @property
    def page(self) -> List[Any]:
        """Returns the sliced page of data."""
        return self.data[self.start_index : self.end_index]

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.end_index < len(self.data)

    @property
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.start_index > 0


class ArrayConnection:
    """Connection wrapper for array pagination."""

    def __init__(self, paginator: ArrayPaginator):
        self.data = paginator.data
        self.paginator = paginator
        self.page = paginator.page

    @property
    def edges(self) -> List[Dict[str, Any]]:
        """Generate edges with cursor and node information"""
        return [
            {"cursor": self.paginator.cursor(pos), "node": node}
            for pos, node in enumerate(self.page)
        ]

    @property
    def total_count(self) -> int:
        """Total number of items in the original data"""
        return len(self.data)

    @property
    def start_cursor(self) -> Optional[str]:
        """Cursor for the first item in the page"""
        return self.paginator.cursor(self.paginator.start_index) if self.page else None

    @property
    def end_cursor(self) -> Optional[str]:
        """Cursor for the last item in the page"""
        return (
            self.paginator.cursor(self.paginator.end_index - 1) if self.page else None
        )

    @property
    def page_info(self) -> Dict[str, Any]:
        """Pagination information"""
        return {
            "has_next_page": self.paginator.has_next,
            "has_previous_page": self.paginator.has_previous,
            "start_cursor": self.start_cursor,
            "end_cursor": self.end_cursor,
        }


class DictCursorPaginator(CursorPaginator):
    """
    WARNING: DictCursorPaginator does not work for dict objects where a key contains the following string: "__"
    TODO: if instance is a dictionary and not an object, don't split the ordering

    ordering = "test__name"
    Django object:
    -> obj.test.name

    Dict:
    -> obj["test"]["name"] X wrong
    we want obj["test__name"]

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
    data: QuerySet | list,
    *,
    ordering=None,
    ordering_direction=None,
    first=None,
    after=None,
    last=None,
    before=None,
):
    """
    A method to take a queryset or an array and return it in paginated order based on the cursor pattern.
    Handles both QuerySets (database queries) and arrays (in-memory data).
    """
    if not first and not last:
        first = 25

    if isinstance(data, list):
        array_paginator = ArrayPaginator(
            data, first=first, last=last, after=after, before=before
        )
        return ArrayConnection(array_paginator)

    else:
        ordering = tuple(field_order(field, ordering_direction) for field in ordering)
        paginator = DictCursorPaginator(data, ordering=ordering)
        page = paginator.page(first=first, after=after, last=last, before=before)
        return Connection(data, paginator, page)


@sync_to_async
def queryset_to_connection(*args, **kwargs):
    return queryset_to_connection_sync(*args, **kwargs)
