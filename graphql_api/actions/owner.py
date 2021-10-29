from asgiref.sync import sync_to_async

from codecov_auth.models import Owner, Session
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
    long_service = get_long_service_name(service)
    return Owner.objects.filter(username=username, service=long_service).first()


def get_owner_sessions(current_user):
    return current_user.session_set.all()
