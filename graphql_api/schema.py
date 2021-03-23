from ariadne import QueryType, gql, make_executable_schema, snake_case_fallback_resolvers
from ariadne.asgi import GraphQL

from .types import types, bindables

schema = make_executable_schema(types, *bindables, snake_case_fallback_resolvers)
