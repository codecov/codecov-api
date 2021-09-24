from asgiref.sync import sync_to_async

from utils.services import get_long_service_name
from codecov_auth.models import Owner, Session


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


@sync_to_async
def create_api_token(current_user, name):
    type = Session.SessionType.API
    return Session.objects.create(name=name, owner=current_user, type=type)


@sync_to_async
def delete_session(current_user, sessionid):
    return Session.objects.filter(sessionid=sessionid, owner=current_user).delete()


def current_user_part_of_org(current_user, org):
    if not current_user.is_authenticated:
        return False
    if current_user == org:
        return True
    # user is a direct member of the org
    orgs_of_user = current_user.organizations or []
    return org.ownerid in orgs_of_user
