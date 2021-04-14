from django.test import TestCase, RequestFactory
from unittest.mock import patch
from codecov_auth.views.base import LoginMixin
from codecov_auth.tests.factories import OwnerFactory


class LoginMixinTests(TestCase):
    def setUp(self):
        self.mixin_instance = LoginMixin()
        self.mixin_instance.cookie_prefix = "github"
        self.request = RequestFactory().get("", {})

    @patch("services.segment.SegmentService.identify_user")
    def test_get_or_create_user_calls_segment_identify_user(self, identify_user_mock):
        self.mixin_instance._get_or_create_user(
            {
                "user": {
                    "id": 12345,
                    "access_token": "4567",
                    "login": "testuser",
                },
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
                "user": {
                    "id": 12345,
                    "access_token": "4567",
                    "login": "testuser",
                },
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
