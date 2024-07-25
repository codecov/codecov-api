from django.conf import settings
from django.urls import path, re_path

from .views.bitbucket import BitbucketLoginView
from .views.bitbucket_server import BitbucketServerLoginView
from .views.github import GithubLoginView
from .views.github_enterprise import GithubEnterpriseLoginView
from .views.gitlab import GitlabLoginView
from .views.gitlab_enterprise import GitlabEnterpriseLoginView
from .views.logout import logout_view
from .views.okta import OktaLoginView
from .views.okta_cloud import OktaCloudCallbackView, OktaCloudLoginView
from .views.sentry import SentryLoginView

urlpatterns = [
    path("logout", logout_view, name="logout"),
    path("logout/<str:service>", logout_view, name="logout-service"),
    path("login/github", GithubLoginView.as_view(), name="github-login"),
    path("login/gh", GithubLoginView.as_view(), name="gh-login"),
    path("login/gitlab", GitlabLoginView.as_view(), name="gitlab-login"),
    path("login/gl", GitlabLoginView.as_view(), name="gl-login"),
    path("login/bitbucket", BitbucketLoginView.as_view(), name="bitbucket-login"),
    path("login/bb", BitbucketLoginView.as_view(), name="bb-login"),
    re_path(
        r"login/github[-_]enterprise/?",
        GithubEnterpriseLoginView.as_view(),
        name="github-enterprise-login",
    ),
    path("login/ghe", GithubEnterpriseLoginView.as_view(), name="ghe-login"),
    re_path(
        r"login/gitlab[-_]enterprise/?",
        GitlabEnterpriseLoginView.as_view(),
        name="gitlab-enterprise-login",
    ),
    path("login/gle", GitlabEnterpriseLoginView.as_view(), name="gle-login"),
    re_path(
        r"login/bitbucket[-_]server/?",
        BitbucketServerLoginView.as_view(),
        name="bitbucket-server-login",
    ),
    path("login/bbs", BitbucketServerLoginView.as_view(), name="bbs-login"),
    path("login/stash", BitbucketServerLoginView.as_view(), name="stash-login"),
    path("login/sentry", SentryLoginView.as_view(), name="sentry-login"),
    path(
        "login/okta/<str:service>/<str:org_username>",
        OktaCloudLoginView.as_view(),
        name="okta-cloud-login",
    ),
    path(
        "login/okta/callback",
        OktaCloudCallbackView.as_view(),
        name="okta-cloud-callback",
    ),
]
if settings.OKTA_ISS is not None:
    urlpatterns += [path("login/okta", OktaLoginView.as_view(), name="okta-login")]
