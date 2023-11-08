from datetime import datetime
from typing import Optional

from ariadne import ObjectType

from codecov_auth.models import Owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql

user = ariadne_load_local_graphql(__file__, "user.graphql")

user_bindable = ObjectType("User")


@user_bindable.field("username")
def resolve_username(user: Owner, info) -> str:
    return user.username


@user_bindable.field("name")
def resolve_name(user: Owner, info) -> Optional[str]:
    return user.name


@user_bindable.field("avatarUrl")
def resolve_avatar_url(user: Owner, info) -> str:
    return user.avatar_url


@user_bindable.field("student")
def resolve_student(user: Owner, info) -> bool:
    return user.student


@user_bindable.field("studentCreatedAt")
def resolve_student_created_at(user: Owner, info) -> Optional[datetime]:
    return user.student_created_at


@user_bindable.field("studentUpdatedAt")
def resolve_student_updated_at(user: Owner, info) -> Optional[datetime]:
    return user.student_updated_at
