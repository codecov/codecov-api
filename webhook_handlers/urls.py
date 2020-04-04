from django.urls import path, include
from .views.github import GithubWebhookHandler
from .views.bitbucket import BitbucketWebhookHandler
from .views.gitlab import GitLabWebhookHandler


urlpatterns = [
    path('github', GithubWebhookHandler.as_view(), name="github-webhook"),
    path('bitbucket', BitbucketWebhookHandler.as_view(), name="bitbucket-webhook"),
    path('gitlab', GitLabWebhookHandler.as_view(), name="gitlab-webhook")
]
