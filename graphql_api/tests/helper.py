import json
from asgiref.sync import async_to_sync, sync_to_async
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from codecov_auth.helpers import create_signed_value

from codecov_auth.models import Session
from ..views import AriadneView


class GraphQLTestHelper:

    async def gql_request(self, query, provider="gh", user=AnonymousUser()):
        url = f"/graphql/{provider}"
        factory = RequestFactory()
        request = factory.post(
            url,
            {"query": query},
            content_type="application/json"
        )
        request.user = user
        response = await AriadneView(request, service=provider)
        return json.loads(response.content)["data"]


def paginate_connection(connection):
    return [edge["node"] for edge in connection["edges"]]
