AVATAR_GITHUB_BASE_URL = "https://avatars0.githubusercontent.com"
BITBUCKET_BASE_URL = "https://bitbucket.org"
GITLAB_BASE_URL = "https://gitlab.com"
GRAVATAR_BASE_URL = "https://www.gravatar.com"
AVATARIO_BASE_URL = "https://avatars.io"

FREE_PLAN_NAME = "users-free"

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
    **NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
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
