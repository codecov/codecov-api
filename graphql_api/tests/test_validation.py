from graphql import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    parse,
    validate,
)

from ..validation import (
    create_max_aliases_rule,
    create_max_depth_rule,
)


def resolve_field(*args):
    return "test"


QueryType = GraphQLObjectType(
    "Query", {"field": GraphQLField(GraphQLString, resolve=resolve_field)}
)
schema = GraphQLSchema(query=QueryType)


def validate_query(query, *rules):
    ast = parse(query)
    return validate(schema, ast, rules=rules)


def test_max_depth_rule_allows_within_depth():
    query = """
    query {
        field
    }
    """
    errors = validate_query(query, create_max_depth_rule(2))
    assert not errors, "Expected no errors for depth within the limit"


def test_max_depth_rule_rejects_exceeding_depth():
    query = """
    query {
        field {
            field {
                field
            }
        }
    }
    """
    errors = validate_query(query, create_max_depth_rule(2))
    assert errors, "Expected errors for exceeding depth limit"
    assert any(
        "Query depth exceeds the maximum allowed depth" in str(e) for e in errors
    )


def test_max_depth_rule_exact_depth():
    query = """
    query {
        field
    }
    """
    errors = validate_query(query, create_max_depth_rule(2))
    assert not errors, "Expected no errors when query depth matches the limit"


def test_max_aliases_rule_allows_within_alias_limit():
    query = """
    query {
        alias1: field
        alias2: field
    }
    """
    errors = validate_query(query, create_max_aliases_rule(2))
    assert not errors, "Expected no errors for alias count within the limit"


def test_max_aliases_rule_rejects_exceeding_alias_limit():
    query = """
    query {
        alias1: field
        alias2: field
        alias3: field
    }
    """
    errors = validate_query(query, create_max_aliases_rule(2))
    assert errors, "Expected errors for exceeding alias limit"
    assert any("Query uses too many aliases" in str(e) for e in errors)


def test_max_aliases_rule_exact_alias_limit():
    query = """
    query {
        alias1: field
        alias2: field
    }
    """
    errors = validate_query(query, create_max_aliases_rule(2))
    assert not errors, "Expected no errors when alias count matches the limit"
