from freezegun import freeze_time
import datetime

from django.test import TransactionTestCase
from ariadne import graphql_sync

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from .helper import GraphQLTestHelper, paginate_connection

query_repositories = """{
    me {
        owner {
            repositories%s {
                totalCount
                edges {
                    node {
                        name
                    }
                }
                pageInfo {
                    hasNextPage
                    %s
                }
            }
        }
    }
}
"""


class TestOwnerType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        random_user = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.user, active=True, private=True, name="a")
        RepositoryFactory(author=self.user, active=False, private=True, name="b")
        RepositoryFactory(author=random_user, active=True, private=True, name="not")
        RepositoryFactory(
            author=random_user, active=True, private=False, name="still-not"
        )

    def test_fetching_repositories(self):
        query = query_repositories % ("", "")
        data = self.gql_request(query, user=self.user)
        assert data == {
            "me": {
                "owner": {
                    "repositories": {
                        "totalCount": 2,
                        "edges": [
                            {"node": {"name": "b"}},
                            {"node": {"name": "a"}},
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                        },
                    }
                }
            }
        }

    def test_fetching_repositories_with_pagination(self):
        query = query_repositories % ("(first: 1)", "endCursor")
        # Check on the first page if we have the repository b
        data_page_one = self.gql_request(query, user=self.user)
        connection = data_page_one["me"]["owner"]["repositories"]
        assert connection["edges"][0]["node"] == {"name": "b"}
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] == True
        next_cursor = pageInfo["endCursor"]
        # Check on the second page if we have the other repository, by using the cursor
        query = query_repositories % (
            f'(first: 1, after: "{next_cursor}")',
            "endCursor",
        )
        data_page_two = self.gql_request(query, user=self.user)
        connection = data_page_two["me"]["owner"]["repositories"]
        assert connection["edges"][0]["node"] == {"name": "a"}
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] == False

    def test_fetching_active_repositories(self):
        query = query_repositories % ("(filters: { active: true })", "")
        data = self.gql_request(query, user=self.user)
        repos = paginate_connection(data["me"]["owner"]["repositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_repositories_by_name(self):
        query = query_repositories % ('(filters: { term: "a" })', "")
        data = self.gql_request(query, user=self.user)
        repos = paginate_connection(data["me"]["owner"]["repositories"])
        assert repos == [{"name": "a"}]
