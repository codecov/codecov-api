from dal import autocomplete
from django.db import connection
from django.http import HttpResponse

from codecov_auth.models import Owner, Service
from core.models import Constants, Repository

_version = None


def _get_version():
    global _version
    if _version is None:
        _version = Constants.objects.get(key="version")
    return _version


def health(request):
    # will raise if connection cannot be established
    connection.ensure_connection()

    version = _get_version()
    return HttpResponse("%s is live!" % version.value)


SERVICE_CHOICES = dict(Service.choices)


class RepositoryAutoCompleteSearch(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # must be authorized to query
        if not self.request.user.is_staff:
            return Repository.objects.none()

        repos = Repository.objects.all()

        terms = self.q.split("/") if self.q else []

        if len(terms) >= 3:
            repos = self.filter_repos_with_three_terms(terms, repos)
        elif len(terms) == 2:
            repos = self.filter_repos_with_two_terms(terms, repos)
        elif len(terms) == 1:
            repos = self.filter_repos_with_one_terms(terms, repos)

        return repos

    def filter_repos_with_three_terms(self, terms, repos):
        assert len(terms) >= 3

        service = terms[0]

        if service not in SERVICE_CHOICES:
            return Repository.objects.none()

        owner = terms[1]
        repo = "/".join(terms[2:])
        return repos.filter(
            author__service=service, author__username=owner, name__startswith=repo
        )

    def filter_repos_with_two_terms(self, terms, repos):
        assert len(terms) == 2

        if terms[0] in SERVICE_CHOICES:
            service = terms[0]
            owner = terms[1]
            return repos.filter(
                author__service=service, author__username__startswith=owner
            )
        else:
            owner = terms[0]
            repo = terms[1]
            return repos.filter(author__username=owner, name__startswith=repo)

    def filter_repos_with_one_terms(self, terms, repos):
        assert len(terms) == 1

        if terms[0] in SERVICE_CHOICES:
            service = terms[0]
            return repos.filter(author__service=service)
        else:
            repo = terms[0]
            return repos.filter(name__startswith=repo)


class OwnerAutoCompleteSearch(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # must be authorized to query
        if not self.request.user.is_staff:
            return Owner.objects.none()

        owners = Owner.objects.all()

        terms = self.q.split("/") if self.q else []

        if len(terms) >= 2:
            owners = self.filter_owners_with_two_terms(terms, owners)
        elif len(terms) == 1:
            owners = self.filter_owners_with_one_term(terms, owners)

        return owners

    def filter_owners_with_two_terms(self, terms, owners):
        assert len(terms) >= 2

        service = terms[0]
        username = "/".join(terms[1:])
        return owners.filter(service=service, username__startswith=username)

    def filter_owners_with_one_term(self, terms, owners):
        assert len(terms) == 1

        if terms[0] in SERVICE_CHOICES:
            service = terms[0]
            return owners.filter(service=service)
        else:
            username = terms[0]
            return owners.filter(username__startswith=username)
