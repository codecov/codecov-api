from django.test import TransactionTestCase

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

                        author {
                            username
                        }
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


class ArianeTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        random_user = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.user, active=True, private=True, name="a")
        RepositoryFactory(author=self.user, active=True, private=True, name="b")
        RepositoryFactory(author=random_user, active=True, private=True, name="not")
        self.user.organizations = [
            OwnerFactory(username="codecov").ownerid,
            OwnerFactory(username="facebook").ownerid,
            OwnerFactory(username="spotify").ownerid,
        ]
        self.user.save()

    def test_when_unauthenticated(self):
        query = "{ me { user { username }} }"
        data = self.gql_request(query)
        assert data == {"me": None}

    def test_when_authenticated(self):
        query = "{ me { user { username avatarUrl }} }"
        data = self.gql_request(query, user=self.user)
        assert data == {
            "me": {
                "user": {
                    "username": self.user.username,
                    "avatarUrl": self.user.avatar_url,
                }
            }
        }

    def test_fetching_repositories(self):
        query = query_repositories % ("", "")
        data = self.gql_request(query, user=self.user)
        assert data == {
            "me": {
                "owner": {
                    "repositories": {
                        "totalCount": 2,
                        "edges": [
                            {
                                "node": {
                                    "name": "b",
                                    "author": {"username": self.user.username},
                                }
                            },
                            {
                                "node": {
                                    "name": "a",
                                    "author": {"username": self.user.username},
                                }
                            },
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
        assert connection["edges"][0]["node"] == {
            "name": "b",
            "author": {"username": self.user.username},
        }
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] is True
        next_cursor = pageInfo["endCursor"]
        # Check on the second page if we have the other repository, by using the cursor
        query = query_repositories % (
            f'(first: 1, after: "{next_cursor}")',
            "endCursor",
        )
        data_page_two = self.gql_request(query, user=self.user)
        connection = data_page_two["me"]["owner"]["repositories"]
        assert connection["edges"][0]["node"] == {
            "name": "a",
            "author": {"username": self.user.username},
        }
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] is False

    def test_fetching_viewable_repositories(self):
        query = """{
            me {
                viewableRepositories {
                    edges {
                        node {
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.gql_request(query, user=self.user)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "b"}, {"name": "a"}]

    def test_fetching_viewable_repositories_text_search(self):
        query = """{
            me {
                viewableRepositories(filters: { term: "a"}) {
                    edges {
                        node {
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.gql_request(query, user=self.user)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_my_orgs(self):
        query = """{
            me {
                myOrganizations {
                    edges {
                        node {
                            username
                        }
                    }
                }
            }
        }
        """
        data = self.gql_request(query, user=self.user)
        orgs = paginate_connection(data["me"]["myOrganizations"])
        assert orgs == [
            {"username": "spotify"},
            {"username": "facebook"},
            {"username": "codecov"},
        ]

    def test_fetching_my_orgs_with_search(self):
        query = """{
            me {
                myOrganizations(filters: { term: "spot"}) {
                    edges {
                        node {
                            username
                        }
                    }
                }
            }
        }
        """
        data = self.gql_request(query, user=self.user)
        orgs = paginate_connection(data["me"]["myOrganizations"])
        assert orgs == [
            {"username": "spotify"},
        ]
