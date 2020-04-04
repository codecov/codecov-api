from django.urls import path, include
from .views.github import GithubWebhookHandler
from .views.gitlab import GitLabWebhookHandler


urlpatterns = [
    path('github', GithubWebhookHandler.as_view(), name="github-webhook"),
    path('gitlab', GitLabWebhookHandler.as_view(), name="gitlab-webhook")
]
