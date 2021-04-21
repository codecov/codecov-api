from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from .helper import GraphQLTestHelper, paginate_connection


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

    def test_fetching_viewable_repositories(self):
        org_1 = OwnerFactory()
        org_2 = OwnerFactory()
        current_user = OwnerFactory(organizations=[org_1.ownerid])
        repos_in_db = [
            RepositoryFactory(private=True, name="0"),
            RepositoryFactory(author=org_1, private=False, name="1"),
            RepositoryFactory(author=org_1, private=True, name="2"),
            RepositoryFactory(author=org_2, private=False, name="3"),
            RepositoryFactory(author=org_2, private=True, name="4"),
            RepositoryFactory(private=True, name="5"),
            RepositoryFactory(author=current_user, private=True, name="6"),
            RepositoryFactory(author=current_user, private=False, name="7"),
        ]
        current_user.permission = [repos_in_db[2].repoid]
        current_user.save()
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
        data = self.gql_request(query, user=current_user)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        repos_name = [repo["name"] for repo in repos]
        assert sorted(repos_name) == [
            "1",  # public repo in org of user
            "2",  # private repo in org of user and in user permission
            "6",  # personal private repo
            "7",  # personal public repo
        ]

    def test_fetching_viewable_repositories_ordering(self):
        current_user = OwnerFactory()

        def build_query(ordering="", ordering_direction=""):
            params = tuple()
            if ordering:
                params += (f"ordering: {ordering}",)
            if ordering_direction:
                params += (f"orderingDirection: {ordering_direction}",)

            query = """{
                me {
                    viewableRepositories%s {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
            }
            """ % (
                f"({','.join(params)})" if params else ""
            )
            return query

        repo_1 = RepositoryFactory(author=current_user, name="A")
        repo_2 = RepositoryFactory(author=current_user, name="B")
        repo_3 = RepositoryFactory(author=current_user, name="C")

        with self.subTest("No ordering (defaults to order by repoid)"):
            with self.subTest("no ordering Direction"):
                data = self.gql_request(build_query(), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    build_query(ordering_direction="ASC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    build_query(ordering_direction="DESC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("NAME"):
            with self.subTest("no ordering Direction"):
                data = self.gql_request(build_query("NAME"), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

            with self.subTest("ASC"):
                data = self.gql_request(build_query("NAME", "ASC"), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(build_query("NAME", "DESC"), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("COMMIT_DATE"):
            # Call save to make sure they have `updatestamp` in chronological order
            repo_1.save()
            repo_2.save()
            repo_3.save()

            with self.subTest("no ordering Direction"):
                data = self.gql_request(build_query("COMMIT_DATE"), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    build_query("COMMIT_DATE", "ASC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    build_query("COMMIT_DATE", "DESC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("COVERAGE"):
            repo_1.cache = {"commit": {"totals": {"c": "42"}}}
            repo_1.save()

            repo_2.cache = {"commit": {"totals": {"c": "100.2"}}}
            repo_2.save()

            repo_3.cache = {"commit": {"totals": {"c": "0"}}}
            repo_3.save()

            with self.subTest("no ordering Direction"):
                data = self.gql_request(build_query("COVERAGE"), user=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["B", "A", "C"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    build_query("COVERAGE", "ASC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "A", "B"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    build_query("COVERAGE", "DESC"), user=current_user
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["B", "A", "C"])

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
