from django.urls import path

from .views.bitbucket import BitbucketLoginView
from .views.bitbucket_server import BitbucketServerLoginView
from .views.github import GithubLoginView
from .views.github_enterprise import GithubEnterpriseLoginView
from .views.gitlab import GitlabLoginView
from .views.gitlab_enterprise import GitlabEnterpriseLoginView
from .views.logout import logout_view

urlpatterns = [
    path("logout/<str:service>", logout_view, name="logout"),
    path("login/github", GithubLoginView.as_view(), name="github-login"),
    path("login/gh", GithubLoginView.as_view(), name="gh-login"),
    path("login/gitlab", GitlabLoginView.as_view(), name="gitlab-login"),
    path("login/gl", GitlabLoginView.as_view(), name="gl-login"),
    path("login/bitbucket", BitbucketLoginView.as_view(), name="bitbucket-login"),
    path("login/bb", BitbucketLoginView.as_view(), name="bb-login"),
    path(
        "login/github-enterprise",
        GithubEnterpriseLoginView.as_view(),
        name="github-enterprise-login",
    ),
    path("login/ghe", GithubEnterpriseLoginView.as_view(), name="ghe-login"),
    path(
        "login/gitlab-enterprise",
        GitlabEnterpriseLoginView.as_view(),
        name="gitlab-enterprise-login",
    ),
    path("login/gle", GitlabEnterpriseLoginView.as_view(), name="gle-login"),
    path(
        "login/bitbucket-server",
        BitbucketServerLoginView.as_view(),
        name="bitbucket-server-login",
    ),
    path("login/bbs", BitbucketServerLoginView.as_view(), name="bbs-login"),
]
