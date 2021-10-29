from unittest.mock import patch

from asgiref.sync import sync_to_async

from codecov_auth.tests.factories import SessionFactory


class GraphQLTestHelper:
    @patch("codecov_auth.authentication.decode_token_from_cookie")
    def gql_request(
        self,
        query,
        mock_decode_token_from_cookie,
        provider="gh",
        user=None,
        variables={},
    ):
        url = f"/graphql/{provider}"
        headers = {}

        if user:
            session = SessionFactory(owner=user)
            headers["HTTP_TOKEN_TYPE"] = "github-token"
            mock_decode_token_from_cookie.return_value = session.token
            self.client.cookies["github-token"] = session.token
            self.client.force_login(user)

        response = self.client.post(
            url,
            {"query": query, "variables": variables},
            content_type="application/json",
            **headers,
        )

        return response.json()["data"]


def paginate_connection(connection):
    return [edge["node"] for edge in connection["edges"]]
