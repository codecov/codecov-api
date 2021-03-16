def search_my_owners(current_user, filters = {}):
    term = filters.get('term')
    queryset = current_user.orgs
    if term:
        queryset = queryset.filter(username__contains=term)
    return queryset
