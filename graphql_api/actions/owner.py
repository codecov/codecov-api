from codecov.commands.exceptions import MissingService
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from utils.services import get_long_service_name


def search_my_owners(current_user, filters):
    filters = filters if filters else {}
    term = filters.get("term")
    queryset = current_user.orgs.exclude(username=None)
    if term:
        queryset = queryset.filter(username__contains=term)
    return queryset


@sync_to_async
def get_owner(service, username):
    if not service:
        raise MissingService()

    long_service = get_long_service_name(service)
    return (
        Owner.objects.filter(username=username, service=long_service)
        .prefetch_related("account")
        .first()
    )


def get_owner_login_sessions(current_user):
    return current_user.session_set.filter(type="login").all()


def get_user_tokens(owner: Owner):
    return owner.user_tokens.all()
