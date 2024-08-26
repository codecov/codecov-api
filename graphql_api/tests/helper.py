from codecov_auth.views.okta_cloud import OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY
from utils.test_utils import Client


class GraphQLTestHelper:
    def gql_request(
        self,
        query,
        provider="gh",
        owner=None,
        variables=None,
        with_errors=False,
        okta_signed_in_accounts=[],
    ):
        url = f"/graphql/{provider}"

        if owner:
            self.client = Client()
            self.client.force_login_owner(owner)

            if okta_signed_in_accounts:
                session = self.client.session
                session[OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY] = okta_signed_in_accounts
                session.save()

        response = self.client.post(
            url,
            {"query": query, "variables": variables or {}},
            content_type="application/json",
        )
        return response.json() if with_errors else response.json()["data"]


def paginate_connection(connection):
    return [edge["node"] for edge in connection["edges"]]
