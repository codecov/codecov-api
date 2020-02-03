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
