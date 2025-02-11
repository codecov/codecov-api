from shared.metrics import Counter

WEBHOOKS_RECEIVED = Counter(
    "api_webhooks_received",
    "Incoming webhooks, broken down by service, event type, and action",
    [
        "service",
        "event",
        "action",
    ],
)

WEBHOOKS_ERRORED = Counter(
    "api_webhooks_errored",
    "Webhooks that cannot be processed, broken down by service and error reason",
    [
        "service",
        "event",
        "action",
        "error_reason",
    ],
)
