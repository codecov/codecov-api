from asgiref.sync import sync_to_async
from django.test import AsyncClient


class GraphQLTestHelper:
    async def gql_request(self, query, provider="gh", user=None):
        url = f"/graphql/{provider}"
        async_client = AsyncClient()
        if user:
            await sync_to_async(async_client.force_login)(user)

        response = await async_client.post(
            url, {"query": query}, content_type="application/json"
        )
        return response.json()["data"]


def paginate_connection(connection):
    return [edge["node"] for edge in connection["edges"]]
