class UploadParamsParser(object):
    def __init__(self, request_params):
        self.request_params = request_params

    def get(self, value):
        if self.request_params.get("value"):
            return self.request_params.get("value")
        if value in (
            "owner",
            "repo",
            "commit",
            "service",
            "pr",
            "pull_request",
            "branch",
            "job",
            "build",
        ):
            return getattr(self, f"get_{value}")()
