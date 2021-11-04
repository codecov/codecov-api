from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from codecov_auth.views.base import LoginMixin, StateMixin


def set_up_mixin(to=None):
    query_string = {"to": to} if to else None
    mixin = StateMixin()
    mixin.request = RequestFactory().get("", query_string)
    mixin.service = "github"
    return mixin


def test_generate_state_without_redirection_url(mock_redis):
    mixin = set_up_mixin()
    state = mixin.generate_state()
    assert (
        mock_redis.get(f"oauth-state-{state}").decode("utf-8")
        == "http://localhost:3000/gh"
    )


def test_generate_state_with_path_redirection_url(mock_redis):
    mixin = set_up_mixin("/gh/codecov")
    state = mixin.generate_state()
    assert mock_redis.get(f"oauth-state-{state}").decode("utf-8") == "/gh/codecov"


@override_settings(CORS_ALLOWED_ORIGINS=["https://app.codecov.io"])
def test_generate_state_with_safe_domain_redirection_url(mock_redis):
    mixin = set_up_mixin("https://app.codecov.io/gh/codecov")
    state = mixin.generate_state()
    assert (
        mock_redis.get(f"oauth-state-{state}").decode("utf-8")
        == "https://app.codecov.io/gh/codecov"
    )


@override_settings(CORS_ALLOWED_ORIGINS=[])
@override_settings(CORS_ALLOWED_ORIGIN_REGEXES=[r"^(https:\/\/)?(.+)\.codecov\.io$"])
def test_generate_state_with_safe_domain_regex_redirection_url(mock_redis):
    mixin = set_up_mixin("https://app.codecov.io/gh/codecov")
    state = mixin.generate_state()
    assert (
        mock_redis.get(f"oauth-state-{state}").decode("utf-8")
        == "https://app.codecov.io/gh/codecov"
    )


@override_settings(CORS_ALLOWED_ORIGINS=[])
@override_settings(CORS_ALLOWED_ORIGIN_REGEXES=[])
def test_generate_state_with_unsafe_domain(mock_redis):
    mixin = set_up_mixin("http://hacker.com/i-steal-cookie")
    state = mixin.generate_state()
    assert mock_redis.keys("*") != []
    assert (
        mock_redis.get(f"oauth-state-{state}").decode("utf-8")
        == "http://localhost:3000/gh"
    )


@override_settings(CORS_ALLOWED_ORIGINS=[])
@override_settings(CORS_ALLOWED_ORIGIN_REGEXES=[])
def test_generate_state_when_wrong_url(mock_redis):
    mixin = set_up_mixin("http://localhost:]/")
    state = mixin.generate_state()
    assert mock_redis.keys("*") != []
    assert (
        mock_redis.get(f"oauth-state-{state}").decode("utf-8")
        == "http://localhost:3000/gh"
    )


def test_get_redirection_url_from_state_no_state(mock_redis):
    mixin = set_up_mixin()
    with pytest.raises(SuspiciousOperation):
        mixin.get_redirection_url_from_state("not exist")


def test_get_redirection_url_from_state_give_url(mock_redis):
    mixin = set_up_mixin()
    mock_redis.set(f"oauth-state-abc", "http://localhost/gh/codecov")
    assert mixin.get_redirection_url_from_state("abc") == "http://localhost/gh/codecov"


def test_remove_state_with_with_delay(mock_redis):
    mixin = set_up_mixin()
    mock_redis.set(f"oauth-state-abc", "http://localhost/gh/codecov")
    mixin.remove_state("abc", delay=5)
    initial_datetime = datetime.now()
    with freeze_time(initial_datetime) as frozen_time:
        assert mock_redis.get(f"oauth-state-abc") is not None
        frozen_time.move_to(initial_datetime + timedelta(seconds=4))
        assert mock_redis.get(f"oauth-state-abc") is not None
        frozen_time.move_to(initial_datetime + timedelta(seconds=6))
        assert mock_redis.get(f"oauth-state-abc") is None


def test_remove_state_with_with_no_delay(mock_redis):
    mixin = set_up_mixin()
    mock_redis.set(f"oauth-state-abc", "http://localhost/gh/codecov")
    mixin.remove_state("abc")
    assert mock_redis.get(f"oauth-state-abc") is None


class LoginMixinTests(TestCase):
    def setUp(self):
        self.mixin_instance = LoginMixin()
        self.mixin_instance.service = "github"
        self.request = RequestFactory().get("", {})
        self.mixin_instance.request = self.request

    @patch("services.segment.SegmentService.identify_user")
    def test_get_or_create_user_calls_segment_identify_user(self, identify_user_mock):
        self.mixin_instance._get_or_create_user(
            {
                "user": {"id": 12345, "access_token": "4567", "login": "testuser",},
                "has_private_access": False,
            },
            self.request,
        )
        identify_user_mock.assert_called_once()

    @patch("services.segment.SegmentService.user_signed_up")
    def test_get_or_create_calls_segment_user_signed_up_when_owner_created(
        self, user_signed_up_mock
    ):
        self.mixin_instance._get_or_create_user(
            {
                "user": {"id": 12345, "access_token": "4567", "login": "testuser",},
                "has_private_access": False,
            },
            self.request,
        )
        user_signed_up_mock.assert_called_once()

    @patch("services.segment.SegmentService.user_signed_in")
    def test_get_or_create_calls_segment_user_signed_in_when_owner_not_created(
        self, user_signed_in_mock
    ):
        owner = OwnerFactory(service_id=89, service="github")
        self.mixin_instance._get_or_create_user(
            {
                "user": {
                    "id": owner.service_id,
                    "access_token": "02or0sa",
                    "login": owner.username,
                },
                "has_private_access": owner.private_access,
            },
            self.request,
        )
        user_signed_in_mock.assert_called_once()

    @patch("services.segment.SegmentService.user_signed_in")
    def test_set_marketing_tags_on_cookies(self, user_signed_in_mock):
        owner = OwnerFactory(service="github")
        self.request = RequestFactory().get(
            "",
            {
                "utm_department": "a",
                "utm_campaign": "b",
                "utm_medium": "c",
                "utm_source": "d",
                "utm_content": "e",
                "utm_term": "f",
            },
        )
        self.mixin_instance.request = self.request
        response = HttpResponse()
        self.mixin_instance.store_to_cookie_utm_tags(response)
        assert (
            response.cookies["_marketing_tags"].value
            == "utm_department=a&utm_campaign=b&utm_medium=c&utm_source=d&utm_content=e&utm_term=f"
        )

    @patch("services.segment.SegmentService.user_signed_in")
    def test_use_marketing_tags_from_cookies(self, user_signed_in_mock):
        owner = OwnerFactory(service_id=89, service="github")
        self.request.COOKIES[
            "_marketing_tags"
        ] = "utm_department=a&utm_campaign=b&utm_medium=c&utm_source=d&utm_content=e&utm_term=f"
        self.mixin_instance._get_or_create_user(
            {
                "user": {
                    "id": owner.service_id,
                    "access_token": "02or0sa",
                    "login": owner.username,
                },
                "has_private_access": owner.private_access,
            },
            self.request,
        )
        user_signed_in_mock.assert_called_once_with(
            owner,
            **{
                "utm_department": "a",
                "utm_campaign": "b",
                "utm_medium": "c",
                "utm_source": "d",
                "utm_content": "e",
                "utm_term": "f",
            },
        )
