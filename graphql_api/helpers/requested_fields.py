# This was adapted from <https://github.com/mirumee/ariadne/discussions/1116#discussioncomment-6508603>
from collections.abc import Generator, Iterable

from graphql import GraphQLResolveInfo
from graphql.language import (
    FieldNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    SelectionNode,
)


def selected_fields(info: GraphQLResolveInfo) -> set[str]:
    """
    Given a GraphQL "sub-query", this recursively collects all the queried fields.

    For example, if the original GraphQL query looks like `owner { repository { name } }`,
    this would resolve to `repository` and `repository.name`.

    This function works by traversing the parts of the GraphQL Query AST which
    are exposed to each "resolver".
    """
    names: set[str] = set()
    for node in info.field_nodes:
        if node.selection_set is None:
            continue
        names.update(_fields_from_selections(info, node.selection_set.selections))
    return names


def _fields_from_selections(
    info: GraphQLResolveInfo, selections: Iterable[SelectionNode]
) -> Generator[str, None, None]:
    for selection in selections:
        match selection:
            case FieldNode():
                name = selection.name.value
                yield name

                if selection.selection_set is not None:
                    yield from (
                        f"{name}.{field}"
                        for field in _fields_from_selections(
                            info, selection.selection_set.selections
                        )
                    )

            case InlineFragmentNode():
                yield from _fields_from_selections(
                    info, selection.selection_set.selections
                )
            case FragmentSpreadNode():
                fragment = info.fragments[selection.name.value]
                yield from _fields_from_selections(
                    info, fragment.selection_set.selections
                )

            case _:
                raise NotImplementedError(f"field type {type(selection)} not supported")
