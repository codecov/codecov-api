from ariadne import make_executable_schema, snake_case_fallback_resolvers

from .types import bindables, types

# snake_case_fallbck_resolvers gives use a default resolver which convert automatically
# the field name from camelCase to snake_case and try to get it from the object
# see https://ariadnegraphql.org/docs/resolvers#fallback-resolvers
schema = make_executable_schema(types, *bindables, snake_case_fallback_resolvers,)
