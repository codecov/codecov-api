from core.models import Repository


def list_repository_for_owner(current_user, owner):
    queryset = Repository.objects\
        .viewable_repos(current_user)\
        .filter(author=owner)
    return queryset
