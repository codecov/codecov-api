from django.urls import path
from .views import GithubLoginView
from .views.gitlab import GitlabLoginView
from .views.bitbucket import BitbucketLoginView

urlpatterns = [
    path(
        "github",
        GithubLoginView.as_view(),
        name="github-login",
    ),
    path(
        "gh",
        GithubLoginView.as_view(),
        name="gh-login",
    ),
    path(
        "gitlab",
        GitlabLoginView.as_view(),
        name="gitlab-login",
    ),
    path(
        "gl",
        GitlabLoginView.as_view(),
        name="gl-login",
    ),
    path(
        "bitbucket",
        BitbucketLoginView.as_view(),
        name="bitbucket-login",
    ),
    path(
        "bb",
        BitbucketLoginView.as_view(),
        name="bb-login",
    ),
]
