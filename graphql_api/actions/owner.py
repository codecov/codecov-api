from asgiref.sync import sync_to_async

from utils.services import get_long_service_name
from codecov_auth.models import Owner, Session


def search_my_owners(current_user, filters):
    filters = filters if filters else {}
    term = filters.get("term")
    queryset = current_user.orgs
    if term:
        queryset = queryset.filter(username__contains=term)
    return queryset


@sync_to_async
def get_owner(service, username):
    long_service = get_long_service_name(service)
    return Owner.objects.filter(username=username, service=long_service).first()


def get_owner_sessions(current_user):
    return current_user.session_set.all()


@sync_to_async
def create_api_token(current_user, name):
    type = Session.SessionType.API
    return Session.objects.create(name=name, owner=current_user, type=type)
