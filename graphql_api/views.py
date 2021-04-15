from asyncio import iscoroutine
from contextlib import suppress

from asgiref.sync import sync_to_async

from codecov_auth.authentication import CodecovTokenAuthentication

from .ariadne.views import GraphQLView
from .schema import schema
from .tracing import get_tracer_extension


@sync_to_async
def get_user(request):
    with suppress(Exception):
        return CodecovTokenAuthentication().authenticate(request)[0]


BaseAriadneView = GraphQLView.as_view(
    schema=schema, extensions=[get_tracer_extension()]
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
