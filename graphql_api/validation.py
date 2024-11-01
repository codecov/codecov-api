from graphql import GraphQLError, ValidationRule
from graphql.language.ast import DocumentNode, FieldNode, OperationDefinitionNode


def create_max_depth_rule(max_depth: int):
    class MaxDepthRule(ValidationRule):
        def __init__(self, context):
            super().__init__(context)
            self.operation_depth = 1
            self.max_depth_reached = False
            self.max_depth = max_depth

        def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
            self.operation_depth = 1
            self.max_depth_reached = False

        def enter_field(self, node: FieldNode, *_args):
            self.operation_depth += 1

            if self.operation_depth > self.max_depth and not self.max_depth_reached:
                self.max_depth_reached = True
                self.report_error(
                    GraphQLError(
                        f"Query depth exceeds the maximum allowed depth of {self.max_depth}.",
                        node,
                    )
                )

        def leave_field(self, node: FieldNode, *_args):
            self.operation_depth -= 1

    return MaxDepthRule


def create_max_aliases_rule(max_aliases: int):
    class MaxAliasesRule(ValidationRule):
        def __init__(self, context):
            super().__init__(context)
            self.alias_count = 0
            self.has_reported_error = False
            self.max_aliases = max_aliases

        def enter_document(self, node: DocumentNode, *_args):
            self.alias_count = 0
            self.has_reported_error = False

        def enter_field(self, node: FieldNode, *_args):
            if node.alias:
                self.alias_count += 1

                if self.alias_count > self.max_aliases and not self.has_reported_error:
                    self.has_reported_error = True
                    self.report_error(
                        GraphQLError(
                            f"Query uses too many aliases. Maximum allowed is {self.max_aliases}.",
                            node,
                        )
                    )

    return MaxAliasesRule
