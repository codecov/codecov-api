class StripeHTTPHeaders:
    """
    Header-strings associated with Stripe webhook events.
    """

    # https://stripe.com/docs/webhooks/signatures#verify-official-libraries
    SIGNATURE = "HTTP_STRIPE_SIGNATURE"


class StripeWebhookEvents:
    subscribed_events = (
        "invoice.payment_succeeded",
        "invoice.payment_failed",
        "customer.subscription.deleted",
        "customer.created",
        "customer.updated",
        "customer.subscription.created",
        "customer.subscription.updated",
        "checkout.session.completed",
    )
