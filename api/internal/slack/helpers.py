from rest_framework.exceptions import ValidationError


def validate_params(username, service):
    """
    Validates the parameters of the request.
    """
    if not username or not service:
        raise ValidationError("Username and service are required")

    if service not in ["github", "gitlab", "bitbucket"]:
        raise ValidationError("Invalid service")
