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
        "payment_intent.succeeded",
        "setup_intent.succeeded",
        "subscription_schedule.created",
        "subscription_schedule.released",
        "subscription_schedule.updated",
    )


REMOVED_INVOICE_STATUSES = ["draft", "void"]
