from ariadne import make_executable_schema

from .types import bindables, types

# convert_names_case automatically converts the field name from camelCase
# to snake_case. See: https://ariadnegraphql.org/docs/api-reference#optional-arguments-10
schema = make_executable_schema(types, *bindables, convert_names_case=True)
