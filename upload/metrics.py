from shared.metrics import Counter

API_UPLOAD_COUNTER = Counter(
    "api_upload",
    "Total API upload endpoint requests",
    [
        "agent",
        "version",
        "action",
        "endpoint",
        "is_using_shelter",
        "repo_visibility",
        "position",
        "upload_version",
    ],
)
