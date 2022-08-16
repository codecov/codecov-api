import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyQueryTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    RepositoryTokenAuthentication,
)
from codecov_auth.models import RepositoryToken
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory


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
        request = APIRequestFactory().get(f"/endpoint?token={repo.upload_token}")
        authentication = RepositoryLegacyQueryTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is not None
        user, auth = res
        assert user._repository == repo
        assert auth.get_repositories() == [repo]
        assert auth.get_scopes() == ["upload"]
        assert user.is_authenticated()


class TestRepositoryLegacyTokenAuthentication(object):
    def test_authenticate_credentials_empty(self, db):
        token = None
        authentication = RepositoryLegacyTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(token)

    def test_authenticate_credentials_not_uuid(self, db):
        token = "not-a-uuid"
        authentication = RepositoryLegacyTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(token)

    def test_authenticate_credentials_uuid_no_repo(self, db):
        token = str(uuid.uuid4())
        authentication = RepositoryLegacyTokenAuthentication()
        with pytest.raises(exceptions.AuthenticationFailed):
            authentication.authenticate_credentials(token)

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
