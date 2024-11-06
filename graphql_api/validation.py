from typing import Any, Type

from graphql import GraphQLError, ValidationRule
from graphql.language.ast import DocumentNode, FieldNode, OperationDefinitionNode
from graphql.validation import ValidationContext


def create_max_depth_rule(max_depth: int) -> Type[ValidationRule]:
    class MaxDepthRule(ValidationRule):
        def __init__(self, context: ValidationContext) -> None:
            super().__init__(context)
            self.operation_depth: int = 1
            self.max_depth_reached: bool = False
            self.max_depth: int = max_depth

        def enter_operation_definition(
            self, node: OperationDefinitionNode, *_args: Any
        ) -> None:
            self.operation_depth = 1
            self.max_depth_reached = False

        def enter_field(self, node: FieldNode, *_args: Any) -> None:
            self.operation_depth += 1

            if self.operation_depth > self.max_depth and not self.max_depth_reached:
                self.max_depth_reached = True
                self.report_error(
                    GraphQLError(
                        "Query depth exceeds the maximum allowed depth",
                        node,
                    )
                )

        def leave_field(self, node: FieldNode, *_args: Any) -> None:
            self.operation_depth -= 1

    return MaxDepthRule


def create_max_aliases_rule(max_aliases: int) -> Type[ValidationRule]:
    class MaxAliasesRule(ValidationRule):
        def __init__(self, context: ValidationContext) -> None:
            super().__init__(context)
            self.alias_count: int = 0
            self.has_reported_error: bool = False
            self.max_aliases: int = max_aliases

        def enter_document(self, node: DocumentNode, *_args: Any) -> None:
            self.alias_count = 0
            self.has_reported_error = False

        def enter_field(self, node: FieldNode, *_args: Any) -> None:
            if node.alias:
                self.alias_count += 1

                if self.alias_count > self.max_aliases and not self.has_reported_error:
                    self.has_reported_error = True
                    self.report_error(
                        GraphQLError(
                            "Query uses too many aliases",
                            node,
                        )
                    )

    return MaxAliasesRule
