AVATAR_GITHUB_BASE_URL = 'https://avatars0.githubusercontent.com'
BITBUCKET_BASE_URL = 'https://bitbucket.org'
GITLAB_BASE_URL = 'https://gitlab.com'
GRAVATAR_BASE_URL = 'https://www.gravatar.com'
AVATARIO_BASE_URL = 'https://avatars.io'


PAID_USER_PLAN_REPRESENTATIONS = {
    "users-inappm": {
        "marketing_name": "Pro Team",
        "value": "users-inappm",
        "billing_rate": "monthly",
        "base_unit_price": 12,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priorty Support"
        ]
    },
    "users-inappy": {
        "marketing_name": "Pro Team",
        "value": "users-inappy",
        "billing_rate": "annually",
        "base_unit_price": 10,
        "benefits": [
            "Configureable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priorty Support"
        ]
    },
}


USER_PLAN_REPRESENTATIONS = {
    "users-free": {
        "marketing_name": "Basic",
        "value": "users-free",
        "billing_rate": None,
        "base_unit_price": 0,
        "benefits": [
            "Up to 5 users",
            "Unlimited public repositories",
            "Unlimited private repositories"
        ]
    },
    **PAID_USER_PLAN_REPRESENTATIONS
}
