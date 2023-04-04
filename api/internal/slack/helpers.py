from rest_framework.exceptions import ValidationError

from codecov_auth.models import Service


def validate_params(username, service):
    """
    Validates the parameters of the request.
    """
    if not username or not service:
        raise ValidationError("Username and service are required")

    if service not in Service:
        raise ValidationError("Invalid service")
