from typing import TypedDict

from django.conf import settings


# Possible options are defined here: https://ariadnegraphql.org/docs/0.4.0/django-integration#configuration-options
class AriadneDjangoConfigOptions(TypedDict):
    introspection: bool


graphql_config: AriadneDjangoConfigOptions = {
    "introspection": getattr(settings, "GRAPHQL_INTROSPECTION_ENABLED", False),
}
