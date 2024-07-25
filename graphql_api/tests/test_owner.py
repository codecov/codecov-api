import asyncio
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from graphql import GraphQLError
from prometheus_client import REGISTRY
from shared.django_apps.reports.models import ReportType
from shared.upload.utils import UploaderType, insert_coverage_measurement

from codecov.commands.exceptions import MissingService, UnauthorizedGuestAccess
from codecov_auth.models import OwnerProfile
from codecov_auth.tests.factories import (
    AccountFactory,
    GetAdminProviderAdapter,
    OwnerFactory,
    UserFactory,
)
from core.tests.factories import CommitFactory, RepositoryFactory
from plan.constants import PlanName, TrialStatus
from reports.tests.factories import CommitReportFactory, UploadFactory

from .helper import GraphQLTestHelper, paginate_connection

query_repositories = """{
    owner(username: "%s") {
        delinquent
        orgUploadToken
        ownerid
        isCurrentUserPartOfOrg
        yaml
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
"""


class TestOwnerType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.account = AccountFactory()
        self.owner = OwnerFactory(
            username="codecov-user", service="github", account=self.account
        )
        random_user = OwnerFactory(username="random-user", service="github")
        RepositoryFactory(
            author=self.owner, active=True, activated=True, private=True, name="a"
        )
        RepositoryFactory(
            author=self.owner, active=False, private=False, activated=False, name="b"
        )
        RepositoryFactory(
            author=random_user, active=True, activated=False, private=True, name="not"
        )
        RepositoryFactory(
            author=random_user,
            active=True,
            private=False,
            activated=True,
            name="still-not",
        )

    def test_fetching_repositories(self):
        before = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        errors_before = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        timer_before = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data == {
            "owner": {
                "delinquent": None,
                "orgUploadToken": None,
                "ownerid": self.owner.ownerid,
                "isCurrentUserPartOfOrg": True,
                "yaml": None,
                "repositories": {
                    "totalCount": 2,
                    "edges": [{"node": {"name": "a"}}, {"node": {"name": "b"}}],
                    "pageInfo": {"hasNextPage": False},
                },
            }
        }
        after = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        errors_after = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        timer_after = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "owner"},
        )
        assert after - before == 1
        assert errors_after - errors_before == 0
        assert timer_after - timer_before == 1

    def test_fetching_repositories_with_pagination(self):
        query = query_repositories % (self.owner.username, "(first: 1)", "endCursor")
        # Check on the first page if we have the repository b
        data_page_one = self.gql_request(query, owner=self.owner)
        connection = data_page_one["owner"]["repositories"]
        assert connection["edges"][0]["node"] == {"name": "a"}
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] == True
        next_cursor = pageInfo["endCursor"]
        # Check on the second page if we have the other repository, by using the cursor
        query = query_repositories % (
            self.owner.username,
            f'(first: 1, after: "{next_cursor}")',
            "endCursor",
        )
        data_page_two = self.gql_request(query, owner=self.owner)
        connection = data_page_two["owner"]["repositories"]
        assert connection["edges"][0]["node"] == {"name": "b"}
        pageInfo = connection["pageInfo"]
        assert pageInfo["hasNextPage"] == False

    def test_fetching_active_repositories(self):
        query = query_repositories % (
            self.owner.username,
            "(filters: { active: true })",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_repositories_by_name(self):
        query = query_repositories % (
            self.owner.username,
            '(filters: { term: "a" })',
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_public_repository_when_unauthenticated(self):
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "b"}]

    def test_fetching_repositories_with_ordering(self):
        query = query_repositories % (
            self.owner.username,
            "(ordering: NAME, orderingDirection: DESC)",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "b"}, {"name": "a"}]

    def test_fetching_repositories_inactive_repositories(self):
        query = query_repositories % (
            self.owner.username,
            "(filters: { active: false })",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "b"}]

    def test_fetch_account(self) -> None:
        query = """{
            owner(username: "%s") {
                account {
                    name
                }
            }
        }
        """ % (self.owner.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["account"]["name"] == self.account.name

    def test_fetching_repositories_active_repositories(self):
        query = query_repositories % (
            self.owner.username,
            "(filters: { active: true })",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_repositories_activated_repositories(self):
        query = query_repositories % (
            self.owner.username,
            "(filters: { activated: true })",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "a"}]

    def test_fetching_repositories_deactivated_repositories(self):
        query = query_repositories % (
            self.owner.username,
            "(filters: { activated: false })",
            "",
        )
        data = self.gql_request(query, owner=self.owner)
        repos = paginate_connection(data["owner"]["repositories"])
        assert repos == [{"name": "b"}]

    def test_is_part_of_org_when_unauthenticated(self):
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query)
        assert data["owner"]["isCurrentUserPartOfOrg"] is False

    def test_is_part_of_org_when_authenticated_but_not_part(self):
        org = OwnerFactory(username="random_org_test", service="github")
        user = OwnerFactory(username="random_org_user", service="github")
        query = query_repositories % (org.username, "", "")
        data = self.gql_request(query, owner=user)
        assert data["owner"]["isCurrentUserPartOfOrg"] is False

    def test_is_part_of_org_when_user_asking_for_themself(self):
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["isCurrentUserPartOfOrg"] is True

    def test_is_part_of_org_when_user_path_of_it(self):
        org = OwnerFactory(username="random_org_test", service="github")
        user = OwnerFactory(
            username="random_org_user", service="github", organizations=[org.ownerid]
        )
        query = query_repositories % (org.username, "", "")
        data = self.gql_request(query, owner=user)
        assert data["owner"]["isCurrentUserPartOfOrg"] is True

    def test_yaml_when_owner_not_have_yaml(self):
        org = OwnerFactory(username="no_yaml", yaml=None, service="github")
        self.owner.organizations = [org.ownerid]
        self.owner.save()
        query = query_repositories % (org.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["yaml"] is None

    def test_yaml_when_current_user_not_part_of_org(self):
        yaml = {"test": "test"}
        org = OwnerFactory(username="no_yaml", yaml=yaml, service="github")
        self.owner.organizations = []
        self.owner.save()
        query = query_repositories % (org.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["yaml"] is None

    def test_yaml_return_data(self):
        yaml = {"test": "test"}
        org = OwnerFactory(username="no_yaml", yaml=yaml, service="github")
        self.owner.organizations = [org.ownerid]
        self.owner.save()
        query = query_repositories % (org.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["yaml"] == "test: test\n"

    @patch("codecov_auth.commands.owner.owner.OwnerCommands.set_yaml_on_owner")
    def test_repository_dispatch_to_command(self, command_mock):
        asyncio.set_event_loop(asyncio.new_event_loop())
        repo = RepositoryFactory(author=self.owner, private=False)
        query_repositories = """{
            owner(username: "%s") {
                repository(name: "%s") {
                    ... on Repository {
                        name
                    }
                }
            }
        }
        """
        command_mock.return_value = repo
        query = query_repositories % (repo.author.username, repo.name)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["repository"]["name"] == repo.name

    def test_resolve_number_of_uploads_per_user(self):
        query_uploads_number = """{
            owner(username: "%s") {
               numberOfUploads
            }
        }
        """
        repository = RepositoryFactory.create(
            author__plan=PlanName.BASIC_PLAN_NAME.value, author=self.owner
        )
        first_commit = CommitFactory.create(repository=repository)
        first_report = CommitReportFactory.create(
            commit=first_commit, report_type=ReportType.COVERAGE.value
        )
        for i in range(150):
            upload = UploadFactory.create(report=first_report)
            insert_coverage_measurement(
                owner_id=self.owner.ownerid,
                repo_id=repository.repoid,
                commit_id=first_commit.id,
                upload_id=upload.id,
                uploader_used=UploaderType.CLI.value,
                private_repo=repository.private,
                report_type=first_report.report_type,
            )
        query = query_uploads_number % (repository.author.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["numberOfUploads"] == 150

    def test_is_current_user_not_an_admin(self):
        query_current_user_is_admin = """{
            owner(username: "%s") {
               isAdmin
            }
        }
        """
        user = OwnerFactory(username="random_org_user", service="github")
        owner = OwnerFactory(username="random_org_test", service="github")
        query = query_current_user_is_admin % (owner.username)
        data = self.gql_request(query, owner=user, with_errors=True)
        assert data["data"]["owner"]["isAdmin"] is None

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_current_user_an_admin(self, mocked_get_adapter):
        query_current_user_is_admin = """{
            owner(username: "%s") {
               isAdmin
            }
        }
        """
        user = OwnerFactory(username="random_org_admin", service="github")
        owner = OwnerFactory(
            username="random_org_test", service="github", admins=[user.ownerid]
        )
        user.organizations = [owner.ownerid]
        user.save()
        mocked_get_adapter.return_value = GetAdminProviderAdapter()
        query = query_current_user_is_admin % (owner.username)
        data = self.gql_request(query, owner=user)
        assert data["owner"]["isAdmin"] is True

    def test_ownerid(self):
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["ownerid"] == self.owner.ownerid

    def test_delinquent(self):
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["delinquent"] == self.owner.delinquent

    @patch("codecov_auth.commands.owner.owner.OwnerCommands.get_org_upload_token")
    def test_get_org_upload_token(self, mocker):
        mocker.return_value = "upload_token"
        query = query_repositories % (self.owner.username, "", "")
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["orgUploadToken"] == "upload_token"

    # Applies for old users that didn't get their owner profiles created w/ their owner
    def test_when_owner_profile_doesnt_exist(self):
        owner = OwnerFactory(username="no-profile-user")
        owner.profile.delete()
        query = """{
            owner(username: "%s") {
                defaultOrgUsername
                username
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=owner)
        assert data["owner"]["defaultOrgUsername"] is None

    def test_get_default_org_username_for_owner(self):
        organization = OwnerFactory(username="sample-org", service="github")
        owner = OwnerFactory(
            username="sample-owner",
            service="github",
            organizations=[organization.ownerid],
        )
        OwnerProfile.objects.filter(owner_id=owner.ownerid).update(
            default_org=organization
        )
        query = """{
            owner(username: "%s") {
                defaultOrgUsername
                username
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=owner)
        assert data["owner"]["defaultOrgUsername"] == organization.username

    def test_owner_without_default_org_returns_null(self):
        owner = OwnerFactory(username="sample-owner", service="github")
        query = """{
            owner(username: "%s") {
                defaultOrgUsername
                username
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=owner)
        assert data["owner"]["defaultOrgUsername"] is None

    def test_owner_without_owner_profile_returns_no_default_org(self):
        owner = OwnerFactory(username="sample-owner", service="github")
        query = """{
            owner(username: "%s") {
                defaultOrgUsername
                username
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=owner)
        assert data["owner"]["defaultOrgUsername"] is None

    def test_is_current_user_not_activated(self):
        owner = OwnerFactory(username="sample-owner", service="github")
        self.owner.organizations = [owner.ownerid]
        self.owner.save()
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["isCurrentUserActivated"] == False

    def test_is_current_user_not_activated_no_current_owner(self):
        owner = OwnerFactory(username="sample-owner", service="github")
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        self.client.force_login(user=UserFactory())
        data = self.gql_request(query, owner=None)
        assert data["owner"]["isCurrentUserActivated"] == False

    def test_is_current_user_activated(self):
        user = OwnerFactory(username="sample-user")
        owner = OwnerFactory(
            username="sample-owner", plan_activated_users=[user.ownerid]
        )
        user.organizations = [owner.ownerid]
        user.save()
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=user)
        assert data["owner"]["isCurrentUserActivated"] == True

    def test_is_current_user_activated_when_plan_activated_users_is_none(self):
        user = OwnerFactory(username="sample-user")
        owner = OwnerFactory(username="sample-owner", plan_activated_users=None)
        user.organizations = [owner.ownerid]
        user.save()
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=user)
        assert data["owner"]["isCurrentUserActivated"] == False

    def test_is_current_user_activated_anonymous(self):
        owner = OwnerFactory(username="sample-owner")
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query)
        assert data["owner"]["isCurrentUserActivated"] == False

    def test_is_current_user_activated_admin_activated(self):
        owner = OwnerFactory(
            username="sample-owner-authorized",
            admins=[self.owner.ownerid],
            plan_activated_users=[self.owner.ownerid],
        )
        self.owner.organizations = [owner.ownerid]
        self.owner.save()
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["isCurrentUserActivated"] == True

    def test_is_current_user_activated_admin_not_activated(self):
        owner = OwnerFactory(
            username="sample-owner-authorized",
            admins=[self.owner.ownerid],
            plan_activated_users=None,
        )
        self.owner.organizations = [owner.ownerid]
        self.owner.save()
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["isCurrentUserActivated"] == False

    def test_owner_is_current_user_activated(self):
        query = """{
            owner(username: "%s") {
                isCurrentUserActivated
            }
        }
        """ % (self.owner.username)
        data = self.gql_request(query, owner=self.owner)
        assert data["owner"]["isCurrentUserActivated"] == True

    @freeze_time("2023-06-19")
    def test_owner_plan_status(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
            trial_status=TrialStatus.ONGOING.value,
        )
        query = """{
            owner(username: "%s") {
                plan {
                    trialStatus
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["plan"] == {
            "trialStatus": "ONGOING",
        }

    @freeze_time("2023-06-19")
    def test_owner_pretrial_plan_benefits(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
            trial_status=TrialStatus.ONGOING.value,
            plan=PlanName.TRIAL_PLAN_NAME.value,
            pretrial_users_count=123,
        )
        query = """{
            owner(username: "%s") {
                pretrialPlan {
                    benefits
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["pretrialPlan"] == {
            "benefits": [
                "Up to 123 users",
                "Unlimited public repositories",
                "Unlimited private repositories",
            ],
        }

    @freeze_time("2023-06-19")
    def test_owner_available_plans(self):
        current_org = OwnerFactory(
            username="random-plan-user-123",
            service="github",
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            pretrial_users_count=123,
        )
        query = """{
            owner(username: "%s") {
                availablePlans {
                    planName
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["availablePlans"] == [
            {"planName": "users-basic"},
            {"planName": "users-pr-inappm"},
            {"planName": "users-pr-inappy"},
            {"planName": "users-teamm"},
            {"planName": "users-teamy"},
        ]

    def test_owner_query_with_no_service(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
        )
        query = """{
            owner(username: "%s") {
                username
            }
        }
        """ % (current_org.username)

        res = self.gql_request(query, provider="", with_errors=True)

        assert res["errors"][0]["message"] == MissingService.message
        assert res["data"]["owner"] is None

    def test_owner_query_with_private_repos(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
        )
        RepositoryFactory(author=current_org, active=True, activated=True, private=True)
        query = """{
            owner(username: "%s") {
                hasPrivateRepos
            }
        }
        """ % (current_org.username)

        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["hasPrivateRepos"] == True

    def test_owner_query_with_public_repos(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
        )
        RepositoryFactory(
            author=current_org,
            active=True,
            activated=True,
            private=False,
            name="test-one",
        )
        RepositoryFactory(
            author=current_org,
            active=True,
            activated=True,
            private=False,
            name="test-two",
        )
        query = """{
            owner(username: "%s") {
                hasPrivateRepos
            }
        }
        """ % (current_org.username)

        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["hasPrivateRepos"] == False

    def test_owner_hash_owner_id(self):
        user = OwnerFactory(username="sample-user")
        owner = OwnerFactory(username="sample-owner", plan_activated_users=None)
        user.organizations = [owner.ownerid]
        user.save()
        query = """{
            owner(username: "%s") {
                hashOwnerid
            }
        }
        """ % (owner.username)
        data = self.gql_request(query, owner=user)
        assert data["owner"]["hashOwnerid"] is not None

    @override_settings(IS_ENTERPRISE=True, GUEST_ACCESS=False)
    def test_fetch_owner_on_unauthenticated_enteprise_guest_access(self):
        owner = OwnerFactory(username="sample-owner", service="github")
        query = """{
            owner(username: "%s") {
                username
            }
        }
        """ % (owner.username)

        try:
            self.gql_request(query)

        except GraphQLError as e:
            assert e.message == UnauthorizedGuestAccess.message
            assert e.extensions["code"] == UnauthorizedGuestAccess.code

    def test_fetch_current_user_is_okta_authenticated(self):
        account = AccountFactory()
        owner = OwnerFactory(username="sample-owner", service="github", account=account)
        owner.save()

        user = OwnerFactory(username="sample-user")
        user.organizations = [owner.ownerid]
        user.save()

        session = self.client.session
        session["okta_signed_in_accounts"] = [account.pk]
        session.save()

        self.client.force_login(user=user)

        query = """{
            owner(username: "%s") {
                isUserOktaAuthenticated
            }
        }
        """ % (owner.username)

        response = self.client.post(
            "/graphql/gh", {"query": query}, content_type="application/json"
        )
        data = response.json()

        assert data["data"]["owner"]["isUserOktaAuthenticated"] == True

    def test_fetch_current_user_is_not_okta_authenticated(self):
        account = AccountFactory()
        owner = OwnerFactory(username="sample-owner", service="github", account=account)
        owner.save()

        user = OwnerFactory(username="sample-user")
        user.organizations = [owner.ownerid]
        user.save()

        session = self.client.session
        session["okta_signed_in_accounts"] = []
        session.save()

        self.client.force_login(user=user)

        query = """{
            owner(username: "%s") {
                isUserOktaAuthenticated
            }
        }
        """ % (owner.username)

        response = self.client.post(
            "/graphql/gh", {"query": query}, content_type="application/json"
        )
        data = response.json()

        assert data["data"]["owner"]["isUserOktaAuthenticated"] == False

    @patch("shared.rate_limits.determine_entity_redis_key")
    @patch("shared.rate_limits.determine_if_entity_is_rate_limited")
    @override_settings(IS_ENTERPRISE=True, GUEST_ACCESS=False)
    def test_fetch_is_github_rate_limited(
        self, mock_determine_rate_limit, mock_determine_redis_key
    ):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
        )
        query = """{
            owner(username: "%s") {
                isGithubRateLimited
            }
        }

        """ % (current_org.username)
        mock_determine_redis_key.return_value = "test"
        mock_determine_rate_limit.return_value = True

        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["isGithubRateLimited"] == True

    def test_fetch_is_github_rate_limited_not_on_gh_service(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="bitbucket",
        )
        query = """{
            owner(username: "%s") {
                isGithubRateLimited
            }
        }

        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org, provider="bb")
        assert data["owner"]["isGithubRateLimited"] == False
