from ariadne import QueryType, gql, make_executable_schema
from ariadne.asgi import GraphQL

from .types import types, bindables

schema = make_executable_schema(types, *bindables)
