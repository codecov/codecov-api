from uuid import uuid4

from rest_framework.test import APIRequestFactory
import pytest
import rest_framework

from utils.test_utils import BaseTestCase
from codecov_auth.tests.factories import SessionFactory
from codecov_auth.authentication import CodecovSessionAuthentication


# Using the standard RequestFactory API to create a form POST request

class TestAuthentication(BaseTestCase):

    def test_auth(self, db):
        a = '2|1:0|10:1546487835|12:github-token|48:MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh|f520039bc6cfb111e4cfc5c3e44fc4fa5921402918547b54383939da803948f4'
        session = SessionFactory.create(token="06ed406d-3fe5-4ff4-baba-349739732b6a")
        request_factory = APIRequestFactory()
        request = request_factory.post('/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'frontend {a}')
        authenticator = CodecovSessionAuthentication()
        result = authenticator.authenticate(request)
        assert result is not None
        user, token = result
        assert user == session.owner
        assert token == session

    def test_auth_no_token(self, db):
        SessionFactory.create()
        token = uuid4()
        request_factory = APIRequestFactory()
        request = request_factory.post(
            '/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'frontend {token}')
        authenticator = CodecovSessionAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.authenticate(request)
