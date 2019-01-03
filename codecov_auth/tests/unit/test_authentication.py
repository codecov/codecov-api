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
        session = SessionFactory.create()
        token = session.token
        request_factory = APIRequestFactory()
        request = request_factory.post('/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'token {token}')
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
            '/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'token {token}')
        authenticator = CodecovSessionAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.authenticate(request)
