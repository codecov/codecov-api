from core.models import Repository


def apply_filters_to_queryset(queryset, filters):
    filters = filters or {}
    term = filters.get("term")
    active = filters.get("active")
    if term:
        queryset = queryset.filter(name__contains=term)
    if active:
        queryset = queryset.filter(active=active)
    return queryset


def list_repository_for_owner(current_user, owner, filters):
    queryset = Repository.objects.viewable_repos(current_user).filter(author=owner)
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset


def search_repos(current_user, filters):
    queryset = Repository.objects.collaborating_repos(current_user)
    queryset = apply_filters_to_queryset(queryset, filters)
    return queryset
