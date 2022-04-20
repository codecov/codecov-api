from django.urls import include, path

# to remove when in production we send the webhooks to /billing/stripe/webhooks
from billing.views import StripeWebhookHandler

from .views.bitbucket import BitbucketWebhookHandler
from .views.github import GithubWebhookHandler
from .views.gitlab import GitLabWebhookHandler

urlpatterns = [
    path("github", GithubWebhookHandler.as_view(), name="github-webhook"),
    path("github_enterprise", GithubWebhookHandler.as_view(), name="github_enterprise-webhook"),
    path("bitbucket", BitbucketWebhookHandler.as_view(), name="bitbucket-webhook"),
    path("gitlab", GitLabWebhookHandler.as_view(), name="gitlab-webhook"),
    path("gitlab_enterprise", GitLabWebhookHandler.as_view(), name="gitlab_enterprise-webhook"),
    path("stripe", StripeWebhookHandler.as_view(), name="old-stripe-webhook"),
]
