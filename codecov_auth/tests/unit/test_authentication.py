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
        a = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        session = SessionFactory.create(token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34")
        request_factory = APIRequestFactory()
        request = request_factory.post('/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'frontend {a}')
        authenticator = CodecovSessionAuthentication()
        result = authenticator.authenticate(request)
        assert result is not None
        user, token = result
        assert user == session.owner
        assert token == session

    def test_decode_token_from_cookie(self):
        val = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        expected_response = "8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34"
        authenticator = CodecovSessionAuthentication()
        assert expected_response == authenticator.decode_token_from_cookie(val)

    def test_decode_token_bad_signature(self):
        val = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|aaaaaaaa7baad2e220faaae02c07c377aaaabca32ad0c2b8baab2aa8cfbe3aaa"
        expected_response = "8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34"
        authenticator = CodecovSessionAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.decode_token_from_cookie(val)

    def test_auth_no_token(self, db):
        SessionFactory.create()
        token = uuid4()
        request_factory = APIRequestFactory()
        request = request_factory.post(
            '/notes/', {'title': 'new idea'}, HTTP_AUTHORIZATION=f'frontend {token}')
        authenticator = CodecovSessionAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.authenticate(request)
