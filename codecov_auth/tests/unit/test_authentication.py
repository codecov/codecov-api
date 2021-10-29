from uuid import uuid4

import pytest
import rest_framework
from django.test import TestCase
from django.urls import ResolverMatch
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.request import Request
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from codecov_auth.authentication import (
    CodecovSessionAuthentication,
    CodecovTokenAuthentication,
)
from codecov_auth.tests.factories import OwnerFactory, SessionFactory
from utils.test_utils import BaseTestCase

# Using the standard RequestFactory API to create a form POST request


def set_resolver_match(request, kwargs={}):
    match = ResolverMatch(func=lambda: None, args=(), kwargs=kwargs)
    request.resolver_match = match


class TestAuthentication(BaseTestCase):
    def test_auth_asd(self, db):
        github_token = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        session = SessionFactory.create(token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34")
        request_factory = APIRequestFactory()
        request_factory.cookies["github-token"] = github_token
        request = request_factory.post(
            "/notes/", {"title": "new idea"}, HTTP_TOKEN_TYPE="github-token"
        )
        set_resolver_match(request)
        authenticator = CodecovTokenAuthentication()
        result = authenticator.authenticate(request)
        assert result is not None
        user, token = result
        assert user == session.owner
        assert token == session

    def test_decode_token_from_cookie(self):
        val = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        expected_response = "8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34"
        authenticator = CodecovTokenAuthentication()
        assert expected_response == authenticator.decode_token_from_cookie(val)

    def test_decode_token_bad_signature(self):
        val = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|aaaaaaaa7baad2e220faaae02c07c377aaaabca32ad0c2b8baab2aa8cfbe3aaa"
        authenticator = CodecovTokenAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.decode_token_from_cookie(val)

    def test_decode_token_bad_cookie_value_format(self):
        val = "2|1:0|10:1557329312|15:bitbucket-token|OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|1335e04704e810cc3096150f30969432ab88116f9679bfcef070b0c5da0e0f23"
        authenticator = CodecovTokenAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.decode_token_from_cookie(val)

    def test_auth_no_token(self, db):
        SessionFactory.create()
        token = uuid4()
        request_factory = APIRequestFactory()
        request_factory.cookies["github-token"] = token
        request = request_factory.post(
            "/notes/", {"title": "new idea"}, HTTP_TOKEN_TYPE="github-token"
        )
        set_resolver_match(request)
        authenticator = CodecovTokenAuthentication()
        with pytest.raises(rest_framework.exceptions.AuthenticationFailed):
            authenticator.authenticate(request)

    def test_verify_session_updates_session(self, db):
        session = SessionFactory.create()
        new_ip, new_user_agent = "0.0.5.6", "Chrome3.99"
        headers = {"HTTP_X_FORWARDED_FOR": new_ip, "User-Agent": new_user_agent}
        request = APIRequestFactory().get("", **headers)
        set_resolver_match(request)
        authenticator = CodecovTokenAuthentication()
        authenticator.update_session(request, session)

        session.refresh_from_db()
        assert session.ip == new_ip
        assert session.useragent == new_user_agent

    def test_verify_session_updates_session_with_remote_addr(self, db):
        """
        This happens when HTTP_X_FORWARDED_FOR header is not present.
        """
        session = SessionFactory.create()
        new_ip, new_user_agent = "0.0.5.6", "Chrome3.99"
        headers = {"REMOTE_ADDR": new_ip, "User-Agent": new_user_agent}
        request = APIRequestFactory().get("", **headers)
        set_resolver_match(request)
        authenticator = CodecovTokenAuthentication()
        authenticator.update_session(request, session)

        session.refresh_from_db()
        assert session.ip == new_ip
        assert session.useragent == new_user_agent

    def test_authenticate_updates_session(self, db, mocker):
        github_token = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        session = SessionFactory.create(token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34")
        request_factory = APIRequestFactory()
        request_factory.cookies["github-token"] = github_token
        request = request_factory.post(
            "/notes/", {"title": "new idea"}, HTTP_TOKEN_TYPE="github-token"
        )
        set_resolver_match(request)
        mocked_verify_session = mocker.patch(
            "codecov_auth.authentication.CodecovTokenAuthentication.update_session"
        )
        authenticator = CodecovTokenAuthentication()
        authenticator.authenticate(request)

        mocked_verify_session.assert_called_once_with(request, session)


class CodecovAuthMixinImpersonationTests(TestCase):
    def setUp(self):
        self.token = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        self.session = SessionFactory(
            token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34", owner=OwnerFactory(staff=True)
        )

        self.user_to_impersonate = "codecov"
        self.impersonated_user = OwnerFactory(username=self.user_to_impersonate)
        self.authenticator = CodecovTokenAuthentication()
        self.request_factory = APIRequestFactory()

    def _create_request(self, cookie="", service=""):
        self.request_factory.cookies["staff_user"] = cookie

        self.request_factory.cookies["github-token"] = self.token
        request = Request(self.request_factory.get("", HTTP_TOKEN_TYPE="github-token"))
        set_resolver_match(
            request, kwargs={"service": service or self.impersonated_user.service}
        )
        return request

    def test_authenticate_returns_owner_according_to_cookie_if_staff(self):
        request = self._create_request(cookie=self.user_to_impersonate)
        user, session = self.authenticator.authenticate(request)
        assert user == self.impersonated_user

    def test_authenticate_raises_permission_denied_if_not_staff(self):
        self.session.owner.staff = False
        self.session.owner.save()

        request = self._create_request(cookie=self.user_to_impersonate)

        with self.assertRaises(PermissionDenied):
            self.authenticator.authenticate(request)

    def test_authentication_fails_if_impersonated_user_doesnt_exist(self):
        self.user_to_impersonate = "scoopy-doo"
        request = self._create_request(
            cookie=self.user_to_impersonate, service="github"
        )

        with self.assertRaises(AuthenticationFailed):
            self.authenticator.authenticate(request)

    def test_impersonation_with_non_github_provider(self):
        non_github_provider = "bitbucket"
        self.impersonated_user.service = non_github_provider
        self.impersonated_user.save()

        request = self._create_request(
            cookie=self.user_to_impersonate, service=non_github_provider
        )

        user, session = self.authenticator.authenticate(request)
        assert user == self.impersonated_user

    def test_impersonation_with_short_git_provider(self):
        non_github_provider = "bitbucket"
        self.impersonated_user.service = non_github_provider
        self.impersonated_user.save()

        request = self._create_request(cookie=self.user_to_impersonate, service="bb")

        user, session = self.authenticator.authenticate(request)
        assert user == self.impersonated_user


class CodecovSessionAuthenticationTests(TestCase):
    def _build_request(self, service, token):
        request_factory = APIRequestFactory()
        request_factory.cookies[f"{service}-token"] = token
        request = request_factory.get("")
        set_resolver_match(request, kwargs={"service": service})
        return request

    def test_cookie_auth_github(self):
        a = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        session = SessionFactory.create(token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34")
        authenticator = CodecovSessionAuthentication()
        request = self._build_request("github", a)
        result = authenticator.authenticate(request)
        assert result is not None
        user, token = result
        assert user == session.owner
        assert token == session

    def test_cookie_auth_bitbucket(self):
        a = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
        session = SessionFactory.create(
            token="8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34",
            owner=OwnerFactory(service="bitbucket"),
        )
        request = self._build_request("bitbucket", a)
        authenticator = CodecovSessionAuthentication()
        result = authenticator.authenticate(request)
        assert result is not None
        user, token = result
        assert user == session.owner
        assert token == session
