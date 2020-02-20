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

    subscribed_members = [PULL_REQUEST, DELETE, PUSH, PUBLIC, STATUS, REPOSITORY]


class WebhookHandlerErrorMessages:
    LICENSE_EXPIRED =  "License expired/invalid. Webhook rejected.",
    INVALID_SIGNATURE = "Invalid signature",
    UNSUPPORTED_EVENT = "Unsupported event",
    SKIP_CODECOV_STATUS = "Ok. Skip Codecov status updates.",
    SKIP_NOT_ACTIVE = "OK. Skip because repo is not active.",
    SKIP_PROCESSING = "OK. Skip because commit not found or is processing.",
    SKIP_PENDING_STATUSES = "Ok. Skip because status is pending."
