import datetime
from http.cookies import SimpleCookie
from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    OktaSettingsFactory,
    UserFactory,
)
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from codecov_auth.models import OwnerProfile

from .helper import GraphQLTestHelper, paginate_connection


class ArianeTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        random_owner = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.owner, active=True, private=True, name="a")
        RepositoryFactory(author=self.owner, active=True, private=False, name="b")
        RepositoryFactory(author=random_owner, active=True, private=True, name="not")
        self.owner.organizations = [
            OwnerFactory(username="codecov").ownerid,
            OwnerFactory(username="facebook").ownerid,
            OwnerFactory(username="spotify").ownerid,
        ]
        self.owner.save()

    def test_when_unauthenticated(self):
        query = "{ me { user { username }} }"
        data = self.gql_request(query)
        assert data == {"me": None}

    def test_when_authenticated(self):
        query = "{ me { user { username avatarUrl }} }"
        data = self.gql_request(query, owner=self.owner)
        assert data == {
            "me": {
                "user": {
                    "username": self.owner.username,
                    "avatarUrl": self.owner.avatar_url,
                }
            }
        }

    def test_when_tracking_metadata(self):
        query = "{ me { trackingMetadata { ownerid } } }"
        data = self.gql_request(query, owner=self.owner)
        assert data == {"me": {"trackingMetadata": {"ownerid": self.owner.ownerid}}}

    def test_when_tracking_metadata_profile(self):
        query = """
        {
            me {
                trackingMetadata {
                    ownerid
                    profile { goals }
                }
            }
        }
        """
        OwnerProfile.objects.filter(owner_id=self.owner.ownerid).update(
            goals=["IMPROVE_COVERAGE"]
        )
        data = self.gql_request(query, owner=self.owner)
        assert data == {
            "me": {
                "trackingMetadata": {
                    "ownerid": self.owner.ownerid,
                    "profile": {"goals": ["IMPROVE_COVERAGE"]},
                }
            }
        }

    def test_when_tracking_metadata_no_profile(self):
        query = """
        {
            me {
                trackingMetadata {
                    ownerid
                    profile { goals }
                }
            }
        }
        """
        data = self.gql_request(query, owner=self.owner)
        assert data == {
            "me": {
                "trackingMetadata": {
                    "ownerid": self.owner.ownerid,
                    "profile": {"goals": []},
                }
            }
        }

    # Applies for old users that didn't get their owner profiles created w/ their owner
    def test_when_owner_profile_doesnt_exist(self):
        query = """
        {
            me {
                trackingMetadata {
                    ownerid
                    profile { goals }
                }
            }
        }
        """
        owner = OwnerFactory(username="another-user")
        owner.profile.delete()
        data = self.gql_request(query, owner=owner)
        assert data == {
            "me": {
                "trackingMetadata": {
                    "ownerid": owner.ownerid,
                    "profile": None,
                }
            }
        }

    def test_private_access_when_private_access_field_is_null(self):
        current_user = OwnerFactory(private_access=None)
        query = """{
            me {
                privateAccess
            }
        }
        """
        data = self.gql_request(query, owner=current_user)
        assert data == {"me": {"privateAccess": False}}

    def test_private_access_when_private_access_field_is_false(self):
        current_user = OwnerFactory(private_access=False)
        query = """{
            me {
                privateAccess
            }
        }
        """
        data = self.gql_request(query, owner=current_user)
        assert data == {"me": {"privateAccess": False}}

    def test_private_access_when_private_access_field_is_true(self):
        current_user = OwnerFactory(private_access=True)
        query = """{
            me {
                privateAccess
            }
        }
        """
        data = self.gql_request(query, owner=current_user)
        assert data == {"me": {"privateAccess": True}}

    def test_fetch_terms_agreement_and_business_email_when_owner_profile_and_user_is_not_null(
        self,
    ):
        current_user = OwnerFactory(
            private_access=True, business_email="testEmail@gmail.com"
        )
        current_user.user.terms_agreement = True
        current_user.user.save()
        query = """{
            me {
                businessEmail
                termsAgreement
            }
        }
        """
        data = self.gql_request(query, owner=current_user)
        assert data == {
            "me": {"businessEmail": "testEmail@gmail.com", "termsAgreement": True}
        }

    def test_fetch_terms_agreement_and_business_email_when_owner_profile_is_null(self):
        current_user = OwnerFactory(private_access=True, business_email=None)
        current_user.profile.delete()
        query = """{
            me {
                businessEmail
                termsAgreement
            }
        }
        """
        data = self.gql_request(query, owner=current_user)
        assert data == {"me": {"businessEmail": None, "termsAgreement": False}}

    def test_fetch_null_terms_agreement_for_user_without_owner(self):
        # There is an edge where an owner without user can call the "me" endpoint
        # via impersonation, in that case return null for terms agreement
        owner_to_impersonate = OwnerFactory()
        owner_to_impersonate.user.delete()
        self.client.cookies = SimpleCookie({"staff_user": owner_to_impersonate.pk})
        self.client.force_login(user=UserFactory(is_staff=True))

        query = """{
            me {
                termsAgreement
            }
        }
        """
        res = self.client.post(
            "/graphql/gh",
            {"query": query},
            content_type="application/json",
        )
        assert res.json()["data"]["me"] == {"termsAgreement": None}

    def test_fetching_viewable_repositories(self):
        org_1 = OwnerFactory()
        org_2 = OwnerFactory()

        authed_account = AccountFactory()
        OktaSettingsFactory(account=authed_account, enforced=True)
        okta_enforced_authenticated = OwnerFactory(account=authed_account)

        unauthed_account = AccountFactory()
        okta_enforced_org_unauth = OwnerFactory(account=unauthed_account)
        OktaSettingsFactory(account=unauthed_account, enforced=True)

        current_user = OwnerFactory(
            organizations=[
                org_1.ownerid,
                okta_enforced_authenticated.ownerid,
                okta_enforced_org_unauth.ownerid,
            ]
        )

        repos_in_db = [
            RepositoryFactory(private=True, name="0"),
            RepositoryFactory(author=org_1, private=False, name="1"),
            RepositoryFactory(author=org_1, private=True, name="2"),
            RepositoryFactory(author=org_2, private=False, name="3"),
            RepositoryFactory(author=org_2, private=True, name="4"),
            RepositoryFactory(private=True, name="5"),
            RepositoryFactory(author=current_user, private=True, name="6"),
            RepositoryFactory(author=current_user, private=False, name="7"),
            RepositoryFactory(
                author=okta_enforced_authenticated,
                private=True,
                name="okta_enforced_repo_authed",
            ),
            RepositoryFactory(
                author=okta_enforced_org_unauth,
                private=True,
                name="okta_enforced_repo_unauthed",
            ),
        ]
        current_user.permission = [
            repos_in_db[2].repoid,
            repos_in_db[8].repoid,
            repos_in_db[9].repoid,
        ]
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
        data = self.gql_request(
            query, owner=current_user, okta_signed_in_accounts=[authed_account.id]
        )
        repos = paginate_connection(data["me"]["viewableRepositories"])
        repos_name = [repo["name"] for repo in repos]
        assert (
            sorted(repos_name)
            == [
                "1",  # public repo in org of user
                "2",  # private repo in org of user and in user permission
                "6",  # personal private repo
                "7",  # personal public repo
                "okta_enforced_repo_authed",  # private repo in org with Okta Enforced permissions
            ]
        )

        # Test with impersonation
        data = self.gql_request(query, owner=current_user, impersonate_owner=True)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        repos_name = [repo["name"] for repo in repos]
        assert (
            sorted(repos_name)
            == [
                "1",  # public repo in org of user
                "2",  # private repo in org of user and in user permission
                "6",  # personal private repo
                "7",  # personal public repo
                "okta_enforced_repo_authed",  # Okta repo should show up for impersonated users
                "okta_enforced_repo_unauthed",  # Okta repo should show up for impersonated users
            ]
        )

    def test_fetching_viewable_repositories_ordering(self):
        current_user = OwnerFactory()
        query = """
            query MeOrderingRespoitories($orderingDirection: OrderingDirection, $ordering: RepositoryOrdering) {
                me {
                    viewableRepositories(orderingDirection: $orderingDirection, ordering: $ordering) {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
            }
        """

        repo_1 = RepositoryFactory(author=current_user, name="A")
        repo_2 = RepositoryFactory(author=current_user, name="B")
        RepositoryFactory(author=current_user, name="C")

        with self.subTest("No ordering (defaults to order by repoid)"):
            with self.subTest("no ordering Direction"):
                data = self.gql_request(query, owner=current_user)
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    query, owner=current_user, variables={"orderingDirection": "ASC"}
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    query, owner=current_user, variables={"orderingDirection": "DESC"}
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("NAME"):
            with self.subTest("no ordering Direction"):
                data = self.gql_request(
                    query, owner=current_user, variables={"ordering": "NAME"}
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "NAME", "orderingDirection": "ASC"},
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "NAME", "orderingDirection": "DESC"},
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("COMMIT_DATE"):
            with self.subTest("no ordering Direction"):
                data = self.gql_request(
                    query, owner=current_user, variables={"ordering": "COMMIT_DATE"}
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "COMMIT_DATE", "orderingDirection": "ASC"},
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["A", "B", "C"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "COMMIT_DATE", "orderingDirection": "DESC"},
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "B", "A"])

        with self.subTest("COVERAGE"):
            hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
            CommitFactory(repository=repo_1, totals={"c": "42"}, timestamp=hour_ago)
            CommitFactory(repository=repo_2, totals={"c": "100.2"}, timestamp=hour_ago)

            # too recent, should not be considered
            CommitFactory(repository=repo_2, totals={"c": "10"})

            with self.subTest("no ordering Direction"):
                data = self.gql_request(
                    query, owner=current_user, variables={"ordering": "COVERAGE"}
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "A", "B"])

            with self.subTest("ASC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "COVERAGE", "orderingDirection": "ASC"},
                )
                repos = paginate_connection(data["me"]["viewableRepositories"])
                repos_name = [repo["name"] for repo in repos]
                self.assertEqual(repos_name, ["C", "A", "B"])

            with self.subTest("DESC"):
                data = self.gql_request(
                    query,
                    owner=current_user,
                    variables={"ordering": "COVERAGE", "orderingDirection": "DESC"},
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
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_viewable_repositories_with_repo_names_search(self):
        query = """{
            me {
                viewableRepositories (filters: { repoNames: ["a", "b"] }) {
                    edges {
                        node {
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "a"}, {"name": "b"}]

    def test_fetching_viewable_repositories_with_is_public(self):
        query = """{{
            me {{
                viewableRepositories (filters: {{ {0} }}) {{
                    edges {{
                        node {{
                            name
                        }}
                    }}
                }}
            }}
        }}
        """
        # isPublic=True (only public) -> b
        data = self.gql_request(query.format("isPublic: true"), owner=self.owner)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "b"}]
        # isPublic=False (only private) -> a
        data = self.gql_request(query.format("isPublic: false"), owner=self.owner)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "a"}]
        # isPublic is not specified (both public and private) -> a,b
        data = self.gql_request(query.format(""), owner=self.owner)
        repos = paginate_connection(data["me"]["viewableRepositories"])
        assert repos == [{"name": "a"}, {"name": "b"}]

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
        data = self.gql_request(query, owner=self.owner)
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
        data = self.gql_request(query, owner=self.owner)
        orgs = paginate_connection(data["me"]["myOrganizations"])

        assert orgs == [{"username": "spotify"}]

    def test_sync_repo_not_authenticated(self):
        mutation = """
            mutation {
              syncWithGitProvider {
                error {
                  __typename
                }
              }
            }
        """
        mutation_data = self.gql_request(mutation)
        assert (
            mutation_data["syncWithGitProvider"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    @patch("codecov_auth.commands.owner.owner.OwnerCommands.is_syncing")
    @patch("codecov_auth.commands.owner.owner.TriggerSyncInteractor.execute")
    def test_sync_repo(self, mock_trigger_refresh, mock_is_refreshing):
        mock_is_refreshing.return_value = True
        query = """{
            me {
                isSyncingWithGitProvider
            }
        }
        """
        data = self.gql_request(query, owner=self.owner)
        assert data["me"]["isSyncingWithGitProvider"] == True
        mutation = """
            mutation {
              syncWithGitProvider {
                error {
                  __typename
                }
              }
            }
        """
        mutation_data = self.gql_request(mutation, owner=self.owner)
        assert mutation_data["syncWithGitProvider"]["error"] is None
        mock_trigger_refresh.assert_called()
