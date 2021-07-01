from ariadne import format_error
from asyncio import iscoroutine
from contextlib import suppress

from asgiref.sync import sync_to_async

from codecov_auth.authentication import CodecovTokenAuthentication

from .ariadne.views import GraphQLView
from .schema import schema
from .tracing import get_tracer_extension
from .commands.exceptions import BaseException

from .executor import Executor


@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]


class AsyncGraphqlView(GraphQLView):
    schema = schema
    extensions = [get_tracer_extension()]

    async def authenticate(self, request):
        user = await get_user(request)
        if user:
            request.user = user

    async def post(self, request, *args, **kwargs):
        await self.authenticate(request)
        return await super().post(request, *args, **kwargs)

    def context_value(self, request):
        return {
            "request": request,
            "service": request.resolver_match.kwargs["service"],
            "executor": Executor(request),
        }

    def error_formatter(self, error, debug=False):
        if debug:
            # If debug is enabled, reuse Ariadne's formatting logi
            return format_error(error, debug)
        formatted = error.formatted
        formatted["message"] = "INTERNAL SERVER ERROR"
        formatted["type"] = "ServerError"
        # if this is one of our own command exception, we can tell a bit more
        if isinstance(error.original_error, BaseException):
            formatted["message"] = error.original_error.message
            formatted["type"] = type(error.original_error).__name__
        return formatted


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
