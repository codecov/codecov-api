class GitHubHTTPHeaders:
    EVENT = 'HTTP_X_GITHUB_EVENT'
    DELIVERY_TOKEN = 'HTTP_X_GITHUB_DELIVERY'
    SIGNATURE = 'HTTP_X_HUB_SIGNATURE'


class GitHubWebhookEvents:
    PULL_REQUEST = "pull_request"
    DELETE = "delete"
    PUSH = "push"
    PUBLIC = "public"
    STATUS = "status"
    REPOSITORY = "repository"
    PING = "ping"
    INSTALLATION = "installation"
    INSTALLATION_REPOSITORIES = "installation_repositories"
    ORGANIZATION = "organization"
    MARKETPLACE_PURCHASE = "marketplace_purchase"
    MARKETPLACE_SUBSCRIPTION = "marketplace_subscription"

    repository_events = [PULL_REQUEST, DELETE, PUSH, PUBLIC, STATUS, REPOSITORY]


class GitLabHTTPHeaders:
    EVENT = "HTTP_X_GITLAB_EVENT"


class GitLabWebhookEvents:
    MERGE_REQUEST = "Merge Request Hook"
    SYSTEM = "System Hook"
    PUSH = "Push Hook"
    JOB = "Job Hook"

    subscribed_events = {
        "push_events": True,
        "issues_events": False,
        "merge_requests_events": True,
        "tag_push_events": False,
        "note_events": False,
        "job_events": False,
        "build_events": True,
        "pipeline_events": True,
        "wiki_events": False
    }


class WebhookHandlerErrorMessages:
    LICENSE_EXPIRED =  "License expired/invalid. Webhook rejected.",
    INVALID_SIGNATURE = "Invalid signature",
    UNSUPPORTED_EVENT = "Unsupported event",
    SKIP_CODECOV_STATUS = "Ok. Skip Codecov status updates.",
    SKIP_NOT_ACTIVE = "OK. Skip because repo is not active.",
    SKIP_PROCESSING = "OK. Skip because commit not found or is processing.",
    SKIP_PENDING_STATUSES = "Ok. Skip because status is pending."
