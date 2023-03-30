def validate_params(username, service):
    """
    Validates the parameters of the request.
    """
    if not username or not service:
        raise ValueError("Username and service are required")

    if service not in ["github", "gitlab", "bitbucket"]:
        raise ValueError("Invalid service")
