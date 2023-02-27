import json
import logging
import socket
from asyncio import iscoroutine
from contextlib import suppress

from ariadne import format_error

# from .ariadne.views import GraphQLView
from ariadne_django.views import GraphQLAsyncView
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseNotAllowed
from sentry_sdk import capture_exception

from codecov.commands.exceptions import BaseException
from codecov.commands.executor import get_executor_from_request
from codecov.db import sync_to_async
from codecov_auth.authentication import CodecovTokenAuthentication
from services import ServiceException

from .schema import schema

log = logging.getLogger(__name__)


@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]


class AsyncGraphqlView(GraphQLAsyncView):
    schema = schema
    extensions = []

    async def get(self, *args, **kwargs):
        if settings.GRAPHQL_PLAYGROUND:
            return super().get(*args, **kwargs)
        # No GraphqlPlayground if no settings.DEBUG
        return HttpResponseNotAllowed(["POST"])

    async def post(self, request, *args, **kwargs):
        # get request body information
        req_body = json.loads(request.body.decode("utf-8")) if request.body else {}

        # clean up graphql query to remove new lines and extra spaces
        req_body["query"] = req_body["query"].replace("\n", " ")
        req_body["query"] = req_body["query"].replace("  ", "").strip()

        # put everything together for log
        log_data = {
            "server_hostname": socket.gethostname(),
            "request_method": request.method,
            "request_path": request.get_full_path(),
            "request_body": req_body,
        }
        log.info("GraphQL Request", extra=log_data)

        request.user = await get_user(request) or AnonymousUser()
        return await super().post(request, *args, **kwargs)

    def context_value(self, request):
        return {
            "request": request,
            "service": request.resolver_match.kwargs["service"],
            "executor": get_executor_from_request(request),
        }

    def error_formatter(self, error, debug=False):
        # the only wat to check for a malformatted query
        is_bad_query = "Cannot query field" in error.formatted["message"]
        if debug or is_bad_query:
            return format_error(error, debug)
        formatted = error.formatted
        formatted["message"] = "INTERNAL SERVER ERROR"
        formatted["type"] = "ServerError"
        # if this is one of our own command exception, we can tell a bit more
        original_error = error.original_error
        if isinstance(original_error, BaseException) or isinstance(
            original_error, ServiceException
        ):
            formatted["message"] = original_error.message
            formatted["type"] = type(original_error).__name__
        else:
            # otherwise it's not supposed to happen, so we log it
            log.error("GraphQL internal server error", exc_info=original_error)
            capture_exception(original_error)
        return formatted


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
