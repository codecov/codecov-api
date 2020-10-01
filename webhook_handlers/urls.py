from django.urls import path, include
from .views.github import GithubWebhookHandler
from .views.bitbucket import BitbucketWebhookHandler
from .views.gitlab import GitLabWebhookHandler
from .views.stripe import StripeWebhookHandler


urlpatterns = [
    path('github', GithubWebhookHandler.as_view(), name="github-webhook"),
    path('bitbucket', BitbucketWebhookHandler.as_view(), name="bitbucket-webhook"),
    path('gitlab', GitLabWebhookHandler.as_view(), name="gitlab-webhook"),
    path('stripe', StripeWebhookHandler.as_view(), name="stripe-webhook")
]
