import logging
import json

from rest_framework.views import exception_handler
from django.http import HttpResponse
from django.conf import settings


log = logging.getLogger(__name__)


def codecov_exception_handler(exc, context):
    """
    An exception handler to give a generic response
    for 500s. By default DRF doesn't handle 500s, and
    instead passes it along to django which returns
    a '<h>Server Error</h>' html response.
    """
    response = exception_handler(exc, context)

    if response is None and settings.DEBUG is False:
        response = HttpResponse(
            json.dumps({'detail': "Server Error"}),
            content_type="application/json", status=500
        )
    return response
