from django.urls import path
from .views import GithubLoginView
from .views.gitlab import GitlabLoginView
from .views.bitbucket import BitbucketLoginView

urlpatterns = [
    path("github", GithubLoginView.as_view(), name="github-login",),
    path("gitlab", GitlabLoginView.as_view(), name="gitlab-login",),
    path("bitbucket", BitbucketLoginView.as_view(), name="bitbucket-login",),
]
