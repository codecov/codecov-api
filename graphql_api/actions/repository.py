from core.models import Repository

def list_repository_for_owner(current_user, owner):
    queryset = Repository.objects.viewable_repos(current_user).filter(author=owner)
    return queryset


def search_repos(current_user, filters={}):
    filters = filters if filters else {}
    term = filters.get("term")
    active = filters.get("active")
    authors_from = [current_user.ownerid] + (current_user.organizations or [])
    queryset = Repository.objects.filter(author__ownerid__in=authors_from)
    if term:
        queryset = queryset.filter(name__contains=term)
    if active:
        queryset = queryset.filter(active=active)
    return queryset
