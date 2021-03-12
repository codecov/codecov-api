from .query import query, query_bindable
from .me import me, me_bindable
from .user import user, user_bindable

types = [query, me, user]

bindables = [
    query_bindable,
    me_bindable,
    user_bindable
]
