from django.urls import path

from .views import StripeWebhookHandler

urlpatterns = [
    path("stripe/webhooks", StripeWebhookHandler.as_view(), name="stripe-webhook"),
]
