from django.urls import path, include
from .views import GithubWebhookHandler


urlpatterns = [
    path('github', GithubWebhookHandler.as_view(), name="github-webhook")
]
