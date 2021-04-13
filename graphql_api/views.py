from asyncio import iscoroutine
from contextlib import suppress

from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from asgiref.sync import sync_to_async

from codecov_auth.authentication import CodecovTokenAuthentication

from .ariadne.views import GraphQLView
from .schema import schema


@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]


BaseAriadneView = GraphQLView.as_view(
    schema=schema, extensions=[ApolloTracingExtension]
)


async def ariadne_view(request, service):
    user = await get_user(request)
    if user:
        request.user = user
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
