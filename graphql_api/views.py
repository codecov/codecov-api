from contextlib import suppress
from .ariadne.views import GraphQLView

from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from codecov_auth.authentication import CodecovTokenAuthentication
from asgiref.sync import async_to_sync, sync_to_async

from .schema import schema

@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]

BaseAriadneView = GraphQLView.as_view(
    schema=schema,
    extensions=[ApolloTracingExtension]
)

async def AriadneView(request, service):
    user = await get_user(request)
    if user:
        request.user = user
    return await BaseAriadneView(request)

AriadneView.csrf_exempt = True
