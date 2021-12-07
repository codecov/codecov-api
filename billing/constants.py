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


FREE_PLAN_NAME = "users-free"
GHM_PLAN_NAME = "users"
BASIC_PLAN_NAME = "users-basic"


NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS = {
    "users-inappm": {
        "marketing_name": "Pro Team",
        "value": "users-inappm",
        "billing_rate": "monthly",
        "base_unit_price": 12,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
    },
    "users-inappy": {
        "marketing_name": "Pro Team",
        "value": "users-inappy",
        "billing_rate": "annual",
        "base_unit_price": 10,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
    },
}


PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS = {
    "users-pr-inappm": {
        "marketing_name": "Pro Team",
        "value": "users-pr-inappm",
        "billing_rate": "monthly",
        "base_unit_price": 12,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
    },
    "users-pr-inappy": {
        "marketing_name": "Pro Team",
        "value": "users-pr-inappy",
        "billing_rate": "annual",
        "base_unit_price": 10,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
    },
}

GHM_PLAN_REPRESENTATION = {
    GHM_PLAN_NAME: {
        "marketing_name": "Github Marketplace",
        "value": GHM_PLAN_NAME,
        "billing_rate": None,
        "base_unit_price": 12,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
    }
}

USER_PLAN_REPRESENTATIONS = {
    FREE_PLAN_NAME: {
        "marketing_name": "Basic",
        "value": FREE_PLAN_NAME,
        "billing_rate": None,
        "base_unit_price": 0,
        "benefits": [
            "Up to 5 users",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
    },
    BASIC_PLAN_NAME: {
        "marketing_name": "Basic",
        "value": BASIC_PLAN_NAME,
        "billing_rate": None,
        "base_unit_price": 0,
        "monthly_uploads_limit": 250,
        "benefits": [
            "Up to 5 users",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
    },
    **NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **GHM_PLAN_REPRESENTATION,
}


CURRENTLY_OFFERED_PLANS = {
    FREE_PLAN_NAME: {
        "marketing_name": "Basic",
        "value": FREE_PLAN_NAME,
        "billing_rate": None,
        "base_unit_price": 0,
        "benefits": [
            "Up to 5 users",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
    },
    **PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
}
