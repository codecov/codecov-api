from django.urls import path, include
from .views.github import GithubWebhookHandler


urlpatterns = [
    path('github', GithubWebhookHandler.as_view(), name="github-webhook")
]
