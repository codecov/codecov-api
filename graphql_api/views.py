import logging
from asyncio import iscoroutine
from contextlib import suppress

from ariadne import format_error

# from .ariadne.views import GraphQLView
from ariadne_django.views import GraphQLAsyncView
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseNotAllowed
from sentry_sdk import capture_exception

from codecov.commands.exceptions import BaseException
from codecov.commands.executor import get_executor_from_request
from codecov_auth.authentication import CodecovTokenAuthentication

from .schema import schema
from .tracing import get_tracer_extension

log = logging.getLogger(__name__)


@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]


class AsyncGraphqlView(GraphQLAsyncView):
    schema = schema
    extensions = [get_tracer_extension()]

    def get(self, *args, **kwargs):
        if settings.GRAPHQL_PLAYGROUND:
            return super().get(*args, **kwargs)
        # No GraphqlPlayground if no settings.DEBUG
        return HttpResponseNotAllowed(["POST"])

    async def post(self, request, *args, **kwargs):
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
        if isinstance(error.original_error, BaseException):
            formatted["message"] = error.original_error.message
            formatted["type"] = type(error.original_error).__name__
        else:
            # otherwise it's not supposed to happen, so we log it
            log.error("GraphQL internal server error", exc_info=error.original_error)
            capture_exception(error.original_error)
        return formatted


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
