from rest_framework.test import APIRequestFactory
from codecov_auth.authentication.repo_auth import RepositoryLegacyTokenAuthentication
from core.tests.factories import RepositoryFactory


class TestRepositoryLegacyTokenAuthentication(object):
    def test_authenticate_unauthenticated(self):
        request = APIRequestFactory().get("/endpoint")
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_non_uuid_token(self):
        request = APIRequestFactory().get("/endpoint?token=banana")
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_uuid_token_no_repo(self, db):
        request = APIRequestFactory().get(
            "/endpoint?token=testwabzdowkt4kyti9w0hxa33zetsta"
        )
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is None

    def test_authenticate_uuid_token_with_repo(self, db):
        repo = RepositoryFactory.create()
        request = APIRequestFactory().get(f"/endpoint?token={repo.upload_token}")
        authentication = RepositoryLegacyTokenAuthentication()
        res = authentication.authenticate(request)
        assert res is not None
        user, auth = res
        assert user._repository == repo
        assert auth.get_repositories() == [repo]
        assert auth.get_scopes() == ["upload"]
        assert user.is_authenticated()
