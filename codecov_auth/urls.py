from django.urls import path
from .views import GithubLoginView

urlpatterns = [
    path("gh", GithubLoginView.as_view(), name="github-login",),
]
