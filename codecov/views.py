from dal import autocomplete
from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseRedirect

from codecov_auth.models import Owner
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

        if self.q:
            repos = repos.filter(name__icontains=self.q)

        return repos


class OwnerAutoCompleteSearch(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # must be authorized to query
        if not self.request.user.is_staff:
            return Owner.objects.none()

        owners = Owner.objects.all()

        if self.q:
            owners = owners.filter(username__icontains=self.q)

        return owners
