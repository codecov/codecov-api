from django.urls import path

from .views import GithubLoginView
from .views.bitbucket import BitbucketLoginView
from .views.gitlab import GitlabLoginView
from .views.logout import logout_view

urlpatterns = [
    path("logout/<str:service>", logout_view, name="logout"),
    path("login/github", GithubLoginView.as_view(), name="github-login"),
    path("login/gh", GithubLoginView.as_view(), name="gh-login"),
    path("login/gitlab", GitlabLoginView.as_view(), name="gitlab-login"),
    path("login/gl", GitlabLoginView.as_view(), name="gl-login"),
    path("login/bitbucket", BitbucketLoginView.as_view(), name="bitbucket-login"),
    path("login/bb", BitbucketLoginView.as_view(), name="bb-login"),
]
