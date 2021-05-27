from asyncio import iscoroutine
from contextlib import suppress

from asgiref.sync import sync_to_async

from codecov_auth.authentication import CodecovTokenAuthentication

from .ariadne.views import GraphQLView
from .schema import schema
from .tracing import get_tracer_extension

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


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
