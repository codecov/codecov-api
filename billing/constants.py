class StripeHTTPHeaders:
    """
    Header-strings associated with Stripe webhook events.
    """

    # https://stripe.com/docs/webhooks/signatures#verify-official-libraries
    SIGNATURE = "HTTP_STRIPE_SIGNATURE"


class StripeWebhookEvents:
    subscribed_events = (
        "checkout.session.completed",
        "customer.created",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.updated",
        "invoice.payment_failed",
        "invoice.payment_succeeded",
        "subscription_schedule.created",
        "subscription_schedule.released",
        "subscription_schedule.updated",
        "setup_intent.succeeded",
        "setup_intent.payment_method_attached",
        "setup_intent.payment_method_automatically_updated",
        "setup_intent.payment_method_changed",
        "setup_intent.payment_method_expired",
        "setup_intent.payment_method_removed",
        "setup_intent.setup_future_usage_updated",
        "setup_intent.setup_future_usage_expired",
        "setup_intent.setup_future_usage_automatically_updated",
    )


REMOVED_INVOICE_STATUSES = ["draft", "void"]
