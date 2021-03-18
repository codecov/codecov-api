from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from .helper import GraphQLTestHelper

query_repositories = """{
    me {
        owner {
            repositories%s {
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

class GrapheneTestCase(GraphQLTestHelper, TestCase):

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        random_user = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.user, active=True, private=True, name="a")
        RepositoryFactory(author=self.user, active=True, private=True, name="b")
        RepositoryFactory(author=random_user, active=True, private=True, name="not")

    def test_when_unauthenticated(self):
        query = "{ me { user { username }} }"
        data = self.gql_request('/graphql/gh/graphene', query)
        assert data == {'me': None }

    def test_when_authenticated(self):
        self.client.force_login(self.user)
        query = "{ me { user { username }} }"
        data = self.gql_request('/graphql/gh/graphene', query)
        assert data == {
            'me': {
                'user': {
                    'username': self.user.username,
                }
            }
        }

    def test_fetching_repositories(self):
        self.client.force_login(self.user)
        query = query_repositories % ("", "")
        data = self.gql_request('/graphql/gh/graphene', query)
        assert data == {
            'me': {
                'owner': {
                    'repositories': {
                        'edges': [
                            { 'node': { 'name': 'b' } },
                            { 'node': { 'name': 'a' } },
                        ],
                        'pageInfo': {
                            'hasNextPage': False,
                        }
                    }
                }
            }
        }

    def test_fetching_repositories_with_pagination(self):
        self.client.force_login(self.user)
        query = query_repositories % ("(first: 1)", "endCursor")
        # Check on the first page if we have the repository b
        data_page_one = self.gql_request('/graphql/gh/graphene', query)
        connection = data_page_one['me']['owner']['repositories']
        assert connection['edges'][0]['node'] == { "name": 'b' }
        pageInfo = connection['pageInfo']
        assert pageInfo['hasNextPage'] == True
        next_cursor = pageInfo['endCursor']
        # Check on the second page if we have the other repository, by using the cursor
        query = query_repositories % (f"(first: 1, after: \"{next_cursor}\")", "endCursor")
        data_page_two = self.gql_request('/graphql/gh/graphene', query)
        connection = data_page_two['me']['owner']['repositories']
        assert connection['edges'][0]['node'] == { "name": 'a' }
        pageInfo = connection['pageInfo']
        assert pageInfo['hasNextPage'] == False
