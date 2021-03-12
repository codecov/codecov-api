from core.models import Repository


def list_repository_for_owner(actor, owner):
    queryset = Repository.objects.filter(author=owner).viewable_repos(actor)
    return queryset
