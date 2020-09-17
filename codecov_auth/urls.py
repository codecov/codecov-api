from django.urls import path
from .views import GithubLoginView
from .views.gitlab import GitlabLoginView

urlpatterns = [
    path("gh", GithubLoginView.as_view(), name="github-login",),
    path("gl", GitlabLoginView.as_view(), name="gitlab-login",),
]
