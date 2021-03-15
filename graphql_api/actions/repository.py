from core.models import Repository


def list_repository_for_owner(actor, owner):
    queryset = Repository.objects\
        .viewable_repos(actor)\
        .filter(author=owner)
    return queryset
