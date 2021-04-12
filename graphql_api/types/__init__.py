from ariadne.contrib.django.scalars import datetime_scalar

from .query import query, query_bindable
from .me import me, me_bindable
from .user import user, user_bindable
from .owner import owner, owner_bindable
from .repository import repository, repository_bindable

types = [query, me, user, owner, repository]

bindables = [
    query_bindable,
    me_bindable,
    user_bindable,
    owner_bindable,
    repository_bindable,
    datetime_scalar
]
