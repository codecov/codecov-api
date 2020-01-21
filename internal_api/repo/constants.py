WEBHOOK_EVENTS = {
    "github": [
        "pull_request",
        "delete",
        "push",
        "public",
        "status",
        "repository"
    ],
    "github_enterprise": [
        "pull_request",
        "delete",
        "push",
        "public",
        "status",
        "repository"
    ],
    "bitbucket": [
        "repo:push", "pullrequest:created", "pullrequest:updated",
        "pullrequest:fulfilled", "repo:commit_status_created",
        "repo:commit_status_updated"
    ],
    # https://confluence.atlassian.com/bitbucketserver/post-service-webhook-for-bitbucket-server-776640367.html
    "bitbucket_server": [],
    "gitlab": {
        "push_events": True,
        "issues_events": False,
        "merge_requests_events": True,
        "tag_push_events": False,
        "note_events": False,
        "job_events": False,
        "build_events": True,
        "pipeline_events": True,
        "wiki_events": False
    },
    "gitlab_enterprise": {
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
}
