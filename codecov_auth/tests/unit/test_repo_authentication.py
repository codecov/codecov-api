import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from codecov_auth.authentication.repo_auth import (
    RepositoryLegacyQueryTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    RepositoryTokenAuthentication,
)
from codecov_auth.models import RepositoryToken
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
