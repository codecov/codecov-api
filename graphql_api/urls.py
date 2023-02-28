from django.urls import re_path

from .views import ariadne_view

ALLOWED_SERVICES = [
    "gh",
    "github",
    "gl",
    "gitlab",
    "bb",
    "bitbucket",
    "ghe",
    "github_enterprise",
    "gle",
    "gitlab_enterprise",
    "bbs",
    "bitbucket_server",
]

service_regex = "|".join(ALLOWED_SERVICES)

urlpatterns = [
    re_path(r"^(?P<service>({}))$".format(service_regex), ariadne_view, name="graphql"),
]
