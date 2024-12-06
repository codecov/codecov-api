from typing import Any, Dict, Type

from graphql import GraphQLError, ValidationRule
from graphql.language.ast import (
    DocumentNode,
    FieldNode,
    OperationDefinitionNode,
    VariableDefinitionNode,
)
from graphql.validation import ValidationContext


class MissingVariablesError(Exception):
    """
    Custom error class to represent errors where required variables defined in the query does
    not have a matching definition in the variables part of the request. Normally when this
    scenario occurs it would raise a GraphQLError type but that would cause a uncaught
    exception for some reason. The aim of this is to surface the error in the response clearly
    and to prevent internal server errors when it occurs.
    """

    pass


def create_required_variables_rule(variables: Dict) -> Type[ValidationRule]:
    class RequiredVariablesValidationRule(ValidationRule):
        def __init__(self, context: ValidationContext) -> None:
            super().__init__(context)
            self.variables = variables

        def enter_operation_definition(
            self, node: OperationDefinitionNode, *_args: Any
        ) -> None:
            # Get variable definitions
            variable_definitions = node.variable_definitions or []

            # Extract variables marked as Non Null
            required_variables = [
                var_def.variable.name.value
                for var_def in variable_definitions
                if isinstance(var_def, VariableDefinitionNode)
                and var_def.type.kind == "non_null_type"
            ]

            # Check if these required variables are provided
            missing_variables = [
                var for var in required_variables if var not in self.variables
            ]
            if missing_variables:
                raise MissingVariablesError(
                    f"Missing required variables: {', '.join(missing_variables)}",
                )

    return RequiredVariablesValidationRule


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
