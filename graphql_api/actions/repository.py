from core.models import Repository


def list_repository_for_owner(current_user, owner):
    queryset = Repository.objects\
        .viewable_repos(current_user)\
        .filter(author=owner)
    return queryset


def search_repos(current_user, filters = {}):
    term = filters.get('term')
    queryset = Repository.objects.viewable_repos(current_user)
    if term:
        queryset = queryset.filter(name__contains=term)
    return queryset
