import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.test import override_settings
from django.utils import timezone
from jwt import PyJWTError
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory
from shared.torngit.exceptions import TorngitObjectNotFoundError, TorngitRateLimitError

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyQueryTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    RepositoryTokenAuthentication,
    TokenlessAuth,
    TokenlessAuthentication,
)
from codecov_auth.models import SERVICE_GITHUB, OrganizationLevelToken, RepositoryToken
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    CommitFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)


class TestRepositoryLegacyQueryTokenAuthentication(object):
    def test_authenticate_unauthenticated(self):
        request = APIRequestFactory().get("/endpoint")
        authentication = RepositoryLegacyQueryTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_non_uuid_token(self):
        request = APIRequestFactory().get("/endpoint?token=banana")
        authentication = RepositoryLegacyQueryTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_uuid_token_no_repo(self, db):
        request = APIRequestFactory().get(
            "/endpoint?token=testwabzdowkt4kyti9w0hxa33zetsta"
        )
        authentication = RepositoryLegacyQueryTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_uuid_token_with_repo(self, db):
        repo = RepositoryFactory.create()
        other_repo = RepositoryFactory.create()
        request = APIRequestFactory().get(f"/endpoint?token={repo.upload_token}")
        authentication = RepositoryLegacyQueryTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is not None
        user, auth = res
        assert user._repository == repo
        assert auth.get_repositories() == [repo]
        assert auth.get_scopes() == ["upload"]
        assert user.is_authenticated()
        assert auth.allows_repo(repo)
        assert not auth.allows_repo(other_repo)


class TestRepositoryLegacyTokenAuthentication(object):
    def test_authenticate_credentials_empty(self, db):
        token = None
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_not_uuid(self, db):
        token = "not-a-uuid"
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_uuid_no_repo(self, db):
        token = str(uuid.uuid4())
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_uuid_token_with_repo(self, db):
        repo = RepositoryFactory.create()
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate_credentials(repo.upload_token)
        assert res is not None
        user, auth = res
        assert user._repository == repo
        assert auth.get_repositories() == [repo]
        assert auth.get_scopes() == ["upload"]


class TestRepositoryTableTokenAuthentication(object):
    def test_authenticate_credentials_empty(self, db):
        key = ""
        authentication = RepositoryTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(key)

    def test_authenticate_credentials_valid_token_no_repo(self, db):
        key = RepositoryToken.generate_key()
        authentication = RepositoryTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(key)

    def test_authenticate_credentials_uuid_token_with_repo(self, db):
        token = RepositoryTokenFactory.create(
            repository__active=True, token_type="profiling"
        )
        authentication = RepositoryTokenAuthentication()
        res = authentication.authenticate_credentials(token.key)
        assert res is not None
        user, auth = res
        assert user._repository == token.repository
        assert auth.get_repositories() == [token.repository]
        assert auth.get_scopes() == ["profiling"]

    def test_authenticate_credentials_uuid_token_with_repo_not_active(self, db):
        token = RepositoryTokenFactory.create(
            repository__active=False, token_type="profiling"
        )
        authentication = RepositoryTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(token.key)

    def test_authenticate_credentials_uuid_token_with_repo_valid_until_not_reached(
        self, db
    ):
        token = RepositoryTokenFactory.create(
            repository__active=True,
            token_type="banana",
            valid_until=timezone.now() + timedelta(seconds=1000),
        )
        authentication = RepositoryTokenAuthentication()
        res = authentication.authenticate_credentials(token.key)
        user, auth = res
        assert user._repository == token.repository
        assert auth.get_repositories() == [token.repository]
        assert auth.get_scopes() == ["banana"]

    def test_authenticate_credentials_uuid_token_with_repo_valid_until_already_reached(
        self, db
    ):
        token = RepositoryTokenFactory.create(
            repository__active=True,
            token_type="banana",
            valid_until=timezone.now() - timedelta(seconds=1000),
        )
        authentication = RepositoryTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed) as exc:
            authentication.authenticate_credentials(token.key)
        assert exc.value.args == ("Invalid token.",)


class TestGlobalTokenAuthentication(object):
    def get_mocked_global_tokens(self):
        return {
            "githubuploadtoken": "github",
            "gitlabuploadtoken": "gitlab",
            "bitbucketserveruploadtoken": "bitbucket_server",
        }

    def test_authentication_for_non_enterprise(self):
        authentication = GlobalTokenAuthentication()
        request = APIRequestFactory().post("/endpoint")
        res = authentication.authenticate(request)
        assert res is None

    @patch("codecov_auth.authentication.repo_auth.get_global_tokens")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_token")
    def test_authentication_for_enterprise_wrong_token(
        self, mocked_token, mocked_get_global_tokens
    ):
        mocked_get_global_tokens.return_value = self.get_mocked_global_tokens()
        mocked_token.return_value = "random_token"
        authentication = GlobalTokenAuthentication()
        request = APIRequestFactory().post("/endpoint")
        res = authentication.authenticate(request)
        assert res is None

    @patch("codecov_auth.authentication.repo_auth.get_global_tokens")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_token")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_owner")
    def test_authentication_for_enterprise_correct_token_repo_not_exists(
        self, mocked_owner, mocked_token, mocked_get_global_tokens, db
    ):
        mocked_get_global_tokens.return_value = self.get_mocked_global_tokens()
        mocked_token.return_value = "githubuploadtoken"
        mocked_owner.return_value = OwnerFactory.create()
        authentication = GlobalTokenAuthentication()
        request = APIRequestFactory().post("/endpoint")
        with pytest.raises(exceptions.AuthenticationFailed) as exc:
            authentication.authenticate(request)
        assert exc.value.args == (
            "Could not find a repository, try using repo upload token",
        )

    @patch("codecov_auth.authentication.repo_auth.get_global_tokens")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_token")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_owner")
    @patch("codecov_auth.authentication.repo_auth.GlobalTokenAuthentication.get_repoid")
    def test_authentication_for_enterprise_correct_token_repo_exists(
        self, mocked_repoid, mocked_owner, mocked_token, mocked_get_global_tokens, db
    ):
        mocked_get_global_tokens.return_value = self.get_mocked_global_tokens()
        mocked_token.return_value = "githubuploadtoken"
        owner = OwnerFactory.create(service="github")
        repoid = 123
        mocked_repoid.return_value = repoid
        mocked_owner.return_value = owner

        repository = RepositoryFactory.create(author=owner, repoid=repoid)
        authentication = GlobalTokenAuthentication()
        request = APIRequestFactory().post("/endpoint")
        res = authentication.authenticate(request)
        assert res is not None
        user, auth = res
        assert user._repository == repository
        assert auth.get_repositories() == [repository]
        assert auth.get_scopes() == ["upload"]


@patch("codecov_auth.authentication.repo_auth.get_repo_with_github_actions_oidc_token")
class TestGitHubOIDCTokenAuthentication(object):
    def test_authenticate_credentials_empty_returns_none(
        self, mocked_get_repo_with_token, db
    ):
        token = None
        authentication = GitHubOIDCTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_uuid_returns_none(
        self, mocked_get_repo_with_token, db
    ):
        token = uuid.uuid4()
        authentication = GitHubOIDCTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_no_repo(self, mocked_get_repo_with_token, db):
        mocked_get_repo_with_token.side_effect = ObjectDoesNotExist()
        token = "the best token"
        authentication = GitHubOIDCTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_oidc_error(self, mocked_get_repo_with_token, db):
        mocked_get_repo_with_token.side_effect = PyJWTError()
        token = "the best token"
        authentication = GitHubOIDCTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is None

    def test_authenticate_credentials_oidc_valid(self, mocked_get_repo_with_token, db):
        token = "the best token"
        repository = RepositoryFactory()
        owner = repository.author
        owner.service = SERVICE_GITHUB
        owner.save()
        mocked_get_repo_with_token.return_value = repository
        authentication = GitHubOIDCTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res is not None
        user, auth = res
        assert auth.get_repositories() == [repository]
        assert auth.allows_repo(repository)
        assert user._repository == repository
        assert auth.get_scopes() == ["upload"]


class TestOrgLevelTokenAuthentication(object):
    @override_settings(IS_ENTERPRISE=True)
    def test_enterprise_no_token_return_none(self, db, mocker):
        authentication = OrgLevelTokenAuthentication()
        token = uuid.uuid4()
        res = authentication.authenticate_credentials(token)
        assert res is None

    @override_settings(IS_ENTERPRISE=False)
    def test_owner_has_no_token_return_none(self, db, mocker):
        token = uuid.uuid4()
        authentication = OrgLevelTokenAuthentication()
        res = authentication.authenticate_credentials(token)
        assert res == None

    @override_settings(IS_ENTERPRISE=False)
    def test_owner_has_token_but_wrong_one_sent_return_none(self, db, mocker):
        owner = OwnerFactory(plan="users-enterprisey")
        owner.save()
        owner_token, _ = OrganizationLevelToken.objects.get_or_create(owner=owner)
        owner_token.save()
        # Valid UUID token but doesn't belong to owner
        wrong_token = uuid.uuid4()
        request = APIRequestFactory().post(
            "/endpoint", HTTP_AUTHORIZATION=f"Token {wrong_token}"
        )
        authentication = OrgLevelTokenAuthentication()
        res = authentication.authenticate(request)
        assert res == None
        assert OrganizationLevelToken.objects.filter(owner=owner).count() == 1

    @override_settings(IS_ENTERPRISE=False)
    def test_expired_token_raises_exception(self, db, mocker):
        owner = OwnerFactory(plan="users-enterprisey")
        owner.save()
        six_hours_ago = datetime.now() - timedelta(hours=6)
        owner_token, _ = OrganizationLevelToken.objects.get_or_create(
            owner=owner, valid_until=six_hours_ago
        )
        owner_token.save()

        request = APIRequestFactory().post(
            "/endpoint", HTTP_AUTHORIZATION=f"Token {owner_token.token}"
        )
        authentication = OrgLevelTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed) as exp:
            authentication.authenticate(request)

        assert exp.match("Token is expired.")

    @override_settings(IS_ENTERPRISE=False)
    def test_orgleveltoken_success_auth(self, db, mocker):
        owner = OwnerFactory(plan="users-enterprisey")
        owner.save()
        week_from_now = datetime.now() + timedelta(days=7)
        owner_token, _ = OrganizationLevelToken.objects.get_or_create(
            owner=owner, valid_until=week_from_now
        )
        owner_token.save()
        repository = RepositoryFactory(author=owner)
        other_repo_from_owner = RepositoryFactory(author=owner)
        random_repo = RepositoryFactory()
        repository.save()
        other_repo_from_owner.save()
        random_repo.save()

        request = APIRequestFactory().post(
            "/endpoint", HTTP_AUTHORIZATION=f"Token {owner_token.token}"
        )
        authentication = OrgLevelTokenAuthentication()
        res = authentication.authenticate(request)

        assert res is not None
        user, auth = res
        assert user == owner
        assert auth.get_repositories() == [other_repo_from_owner, repository]
        assert auth._org == owner
        get_repos_queryset = auth.get_repositories_queryset()
        assert isinstance(get_repos_queryset, QuerySet)
        # We can apply more filters to it
        assert list(
            get_repos_queryset.exclude(repoid=other_repo_from_owner.repoid).all()
        ) == [repository]
        assert auth.allows_repo(repository)
        assert auth.allows_repo(other_repo_from_owner)
        assert not auth.allows_repo(random_repo)

    @override_settings(IS_ENTERPRISE=True)
    def test_orgleveltoken_success_auth_enterprise(self, db, mocker):
        owner = OwnerFactory(plan="users-enterprisey")
        owner.save()
        week_from_now = datetime.now() + timedelta(days=7)
        owner_token, _ = OrganizationLevelToken.objects.get_or_create(
            owner=owner, valid_until=week_from_now
        )
        owner_token.save()
        repository = RepositoryFactory(author=owner)
        other_repo_from_owner = RepositoryFactory(author=owner)
        random_repo = RepositoryFactory()
        repository.save()
        other_repo_from_owner.save()
        random_repo.save()

        request = APIRequestFactory().post(
            "/endpoint", HTTP_AUTHORIZATION=f"Token {owner_token.token}"
        )
        authentication = OrgLevelTokenAuthentication()
        res = authentication.authenticate(request)

        assert res is not None
        user, auth = res
        assert user == owner
        assert auth.get_repositories() == [other_repo_from_owner, repository]
        assert auth._org == owner
        get_repos_queryset = auth.get_repositories_queryset()
        assert isinstance(get_repos_queryset, QuerySet)
        # We can apply more filters to it
        assert list(
            get_repos_queryset.exclude(repoid=other_repo_from_owner.repoid).all()
        ) == [repository]
        assert auth.allows_repo(repository)
        assert auth.allows_repo(other_repo_from_owner)
        assert not auth.allows_repo(random_repo)

    def test_token_is_not_uuid(self):
        """
        OIDC tokens are not UUID, so if you do token = OrganizationLevelToken.objects.filter(token=key).first(),
        you get a ValidationError for trying a non-UUID in a models.UUIDField. Rather than adding a try/except,
        check whether the incoming `key` is a UUID - if not, don't try to find it in OrganizationLevelToken.
        """
        authentication = OrgLevelTokenAuthentication()
        token = "not a uuid"
        res = authentication.authenticate_credentials(token)
        assert res is None


class TestTokenlessAuth(object):
    def test_tokenless_bad_path(self):
        request = APIRequestFactory().post(
            "/endpoint",
            headers={},
        )
        authentication = TokenlessAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            _ = authentication.authenticate(request)

    def test_tokenless_unknown_repository(self, db):
        request = APIRequestFactory().post(
            "/upload/github/owner::::repo/commits/commit_sha/reports/report_code/uploads",
            headers={"X-Tokenless": "user-name/repo-forked", "X-Tokenless-PR": "15"},
        )
        authentication = TokenlessAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            _ = authentication.authenticate(request)

    @pytest.mark.parametrize(
        "request_uri,repo_slug,commitid",
        [
            ("/upload/github/ownerSEPARATORthe_repo/commits", "owner/the_repo", None),
            ("/upload/github/ownerSEPARATORthe_repo/commits/", "owner/the_repo", None),
            (
                "/upload/github/ownerSEPARATORthe_repo/commits/9652fb7ff577f554588ea83afded9000acd084ee/reports",
                "owner/the_repo",
                "9652fb7ff577f554588ea83afded9000acd084ee",
            ),
            (
                "/upload/github/ownerSEPARATORthe_repo/commits/9652fb7ff577f554588ea83afded9000acd084ee/reports/",
                "owner/the_repo",
                "9652fb7ff577f554588ea83afded9000acd084ee",
            ),
            (
                "/upload/github/ownerSEPARATORthe_repo/commits/9652fb7ff577f554588ea83afded9000acd084ee/reports/default/uploads",
                "owner/the_repo",
                "9652fb7ff577f554588ea83afded9000acd084ee",
            ),
            (
                "/upload/github/ownerSEPARATORthe_repo/commits/9652fb7ff577f554588ea83afded9000acd084ee/reports/default/uploads/",
                "owner/the_repo",
                "9652fb7ff577f554588ea83afded9000acd084ee",
            ),
            (
                "/upload/github/ownerSEPARATORexample-repo/commits",
                "owner/example-repo",
                None,
            ),
            (
                "/upload/github/ownerSEPARATOR__example-repo__/commits",
                "owner/__example-repo__",
                None,
            ),
            (
                "/upload/github/ownerSEPARATOR~example-repo:copy/commits",
                "owner/~example-repo:copy",
                None,
            ),
        ],
    )
    def test_tokenless_matches_paths(self, request_uri, repo_slug, commitid, db):
        author_name, repo_name = repo_slug.split("/")
        # Doing this because of ATS.
        # For pytest '::' is the divider between a test class and a test function.
        # There's a non-zero chance that the full test name would be mis-interpreted by pytest
        # And these tests would never work with ATS.
        # Sadly there's no way to escape the '::' sequence
        request_uri = request_uri.replace("SEPARATOR", "::::")
        repo = RepositoryFactory(
            name=repo_name, author__username=author_name, private=False
        )
        assert repo.service == "github"
        request = APIRequestFactory().post(
            request_uri, {"branch": "fork:branch"}, format="json"
        )
        authentication = TokenlessAuthentication()
        assert authentication._get_info_from_request_path(request) == (repo, commitid)

    @pytest.mark.parametrize("private", [False, True])
    @pytest.mark.parametrize("branch", ["branch", "fork:branch"])
    @pytest.mark.parametrize(
        "existing_commit,commit_branch",
        [(False, None), (True, "branch"), (True, "fork:branch")],
    )
    def test_tokenless_success(
        self,
        db,
        mocker,
        private,
        branch,
        existing_commit,
        commit_branch,
    ):
        repo = RepositoryFactory(private=private)

        if existing_commit:
            commit = CommitFactory()
            commit.branch = commit_branch
            commit.save()

            request = APIRequestFactory().post(
                f"/upload/github/{repo.author.username}::::{repo.name}/commits/{commit.commitid}/reports/report_code/uploads",
                {"branch": branch},
                format="json",
            )

        else:
            request = APIRequestFactory().post(
                f"/upload/github/{repo.author.username}::::{repo.name}/commits",
                {"branch": branch},
                format="json",
            )

        authentication = TokenlessAuthentication()
        expected = private is False and (
            (existing_commit is False and ":" in branch)
            or (existing_commit is True and ":" in commit_branch)
        )

        if expected:
            res = authentication.authenticate(request)
            assert res is not None
            repo_as_user, auth_class = res

            assert repo_as_user.is_authenticated() is expected
            assert isinstance(auth_class, TokenlessAuth)
        else:
            with pytest.raises(exceptions.AuthenticationFailed):
                res = authentication.authenticate(request)
