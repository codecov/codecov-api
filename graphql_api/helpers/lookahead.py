from typing import Iterable, Optional

from graphql.language.ast import (
    FragmentSpreadNode,
    Node,
    SelectionSetNode,
    VariableNode,
)
from graphql.type import GraphQLInputType
from graphql.type.definition import GraphQLResolveInfo
from graphql.utilities.value_from_ast import value_from_ast


class LookaheadNode:
    """
    Wrapper around a node in the GraphQL AST that has a set of args
    and potentially some child nodes.
    """

    def __init__(self, node: Node, info: GraphQLResolveInfo):
        self.node = node
        self.info = info

    @property
    def args(self) -> dict[str, any]:
        """
        Return a dict of this node's arguments as a name -> value mapping
        """
        args = {}
        for arg in self.node.arguments:
            name = arg.name.value
            value_node = arg.value
            if isinstance(value_node, VariableNode):
                variable_name = value_node.name.value
                value = self.info.variable_values[variable_name]
            else:
                value = value_node.value
            args[name] = value
        return args

    def __getitem__(self, name: str) -> Optional["LookaheadNode"]:
        """
        Get a child node by name
        """
        if self.node.selection_set:
            for selection in self._flatten_selections(self.node.selection_set):
                if selection.name.value == name:
                    return LookaheadNode(selection, self.info)

    def _flatten_selections(self, selection_set: SelectionSetNode) -> Iterable[Node]:
        """
        Expand fragments into flat list of selections
        """
        selections = []
        for selection in selection_set.selections:
            if isinstance(selection, FragmentSpreadNode):
                fragment = self.info.fragments[selection.name.value]
                for selection in fragment.selection_set.selections:
                    selections.append(selection)
            else:
                selections.append(selection)
        return selections


def lookahead(info: GraphQLResolveInfo, path: Iterable[str]) -> Optional[LookaheadNode]:
    """
    Traverse the GraphQL AST and return the lookahead node at the given `path`
    """
    node = LookaheadNode(info.field_nodes[0], info)

    for item in path:
        if node:
            node = node[item]
        else:
            return None

    return node
