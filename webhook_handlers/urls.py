from django.urls import path

# to remove when in production we send the webhooks to /billing/stripe/webhooks
from billing.views import StripeWebhookHandler

from .views.bitbucket import BitbucketWebhookHandler
from .views.bitbucket_server import BitbucketServerWebhookHandler
from .views.github import GithubEnterpriseWebhookHandler, GithubWebhookHandler
from .views.gitlab import GitLabEnterpriseWebhookHandler, GitLabWebhookHandler

urlpatterns = [
    path("github", GithubWebhookHandler.as_view(), name="github-webhook"),
    path(
        "github_enterprise",
        GithubEnterpriseWebhookHandler.as_view(),
        name="github_enterprise-webhook",
    ),
    path("bitbucket", BitbucketWebhookHandler.as_view(), name="bitbucket-webhook"),
    path("gitlab", GitLabWebhookHandler.as_view(), name="gitlab-webhook"),
    path(
        "gitlab_enterprise",
        GitLabEnterpriseWebhookHandler.as_view(),
        name="gitlab_enterprise-webhook",
    ),
    path(
        "bitbucket_server",
        BitbucketServerWebhookHandler.as_view(),
        name="bitbucket-server-webhook",
    ),
    path("stripe", StripeWebhookHandler.as_view(), name="old-stripe-webhook"),
]
