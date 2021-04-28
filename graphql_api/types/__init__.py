from ariadne import load_schema_from_path
from ariadne.contrib.django.scalars import datetime_scalar

from ..helpers.ariadne import ariadne_load_local_graphql
from .query import query, query_bindable
from .me import me, me_bindable
from .user import user, user_bindable
from .owner import owner, owner_bindable
from .repository import repository, repository_bindable
from .session import session, session_bindable
from .mutation import mutation, mutation_bindable
from .enums import enums, enum_types

inputs = ariadne_load_local_graphql(__file__, "./inputs")
enums = ariadne_load_local_graphql(__file__, "./enums")
types = [query, me, user, owner, repository, inputs, enums, session, mutation]

bindables = [
    query_bindable,
    me_bindable,
    user_bindable,
    owner_bindable,
    repository_bindable,
    session_bindable,
    mutation_bindable,
    datetime_scalar,
    *enum_types.enum_types,
]
