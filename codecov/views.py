from dal import autocomplete
from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseRedirect

from codecov_auth.models import Owner, Service
from core.models import Constants, Repository

_version = None


def _get_version():
    global _version
    if _version is None:
        _version = Constants.objects.get(key="version")
    return _version


def health(request):
    # will raise if connection cannot be estabilished
    connection.ensure_connection()

    version = _get_version()
    return HttpResponse("%s is live!" % version.value)


def redirect_app(request):
    """
    This view is intended to be used as part of the frontend migration to redirect traffic from legacy urls to urls
    """
    app_domain = settings.CODECOV_DASHBOARD_URL
    return HttpResponseRedirect(app_domain + request.path.replace("/redirect_app", ""))


class RepositoryAutoCompleteSearch(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # must be authorized to query
        if not self.request.user.is_staff:
            return Repository.objects.none()

        repos = Repository.objects.all()

        terms = self.q.split("/") if self.q else []

        if len(terms) >= 3:
            service = terms[0]
            owner = terms[1]
            repo = "/".join(terms[2:])
            repos = repos.filter(
                author__service=service, author__username=owner, name__startswith=repo
            )
        elif len(terms) == 2:
            if terms[0] in dict(Service.choices):
                service = terms[0]
                owner = terms[1]
                repos = repos.filter(
                    author__service=service, author__username__startswith=owner
                )
            else:
                owner = terms[0]
                repo = terms[1]
                repos = repos.filter(author__username=owner, name__startswith=repo)
        elif len(terms) == 1:
            if terms[0] in dict(Service.choices):
                service = terms[0]
                repos = repos.filter(author__service=service)
            else:
                repo = terms[0]
                repos = repos.filter(name__startswith=repo)

        return repos


class OwnerAutoCompleteSearch(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # must be authorized to query
        if not self.request.user.is_staff:
            return Owner.objects.none()

        owners = Owner.objects.all()

        terms = self.q.split("/") if self.q else []

        if len(terms) >= 2:
            service = terms[0]
            username = "/".join(terms[1:])
            owners = owners.filter(service=service, username__startswith=username)
        elif len(terms) == 1:
            if terms[0] in dict(Service.choices):
                service = terms[0]
                owners = owners.filter(service=service)
            else:
                username = terms[0]
                owners = owners.filter(username__startswith=username)

        return owners
