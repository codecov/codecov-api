from utils.services import get_long_service_name
from codecov_auth.models import Owner

def search_my_owners(current_user, filters):
    filters = filters if filters else {}
    term = filters.get("term")
    queryset = current_user.orgs
    if term:
        queryset = queryset.filter(username__contains=term)
    return queryset


def get_owner(service, username):
    print(username)
    print(service)
    print(get_long_service_name(service))
    return Owner.objects.filter(
        username=username,
        service=get_long_service_name(service)
    ).first()
