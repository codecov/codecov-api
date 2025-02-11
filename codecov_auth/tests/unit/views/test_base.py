from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import pytest
from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from freezegun import freeze_time
from shared.django_apps.codecov_auth.tests.factories import (
    OwnerFactory,
    SessionFactory,
    UserFactory,
)
from shared.license import LicenseInformation

from codecov_auth.models import DjangoSession, Owner, OwnerProfile, Session
from codecov_auth.tests.factories import DjangoSessionFactory
from codecov_auth.views.base import LoginMixin, StateMixin


def set_up_mixin(to=None):
    query_string = {"to": to} if to else None
    mixin = StateMixin()
    mixin.request = RequestFactory().get("", query_string)
    mixin.request.session = SessionStore()
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


def test_get_redirection_url_from_state_without_redis_state(mock_redis):
    mixin = set_up_mixin()
    assert mixin.get_redirection_url_from_state("not exist") == (
        "http://localhost:3000/gh",
        False,
    )


def test_get_redirection_url_from_state_without_session_state(mock_redis):
    mixin = set_up_mixin()
    state = "abc"
    mock_redis.set(mixin._get_key_redis(state), "http://localhost/gh/codecov")
    assert mixin.get_redirection_url_from_state(state) == (
        "http://localhost:3000",
        False,
    )


def test_get_redirection_url_from_state_with_session_state_mismatch(mock_redis):
    mixin = set_up_mixin()
    state = "abc"
    mock_redis.set(mixin._get_key_redis(state), "http://localhost/gh/codecov")
    mixin.request.session[mixin._session_key()] = "def"

    assert mixin.get_redirection_url_from_state(state) == (
        "http://localhost:3000",
        False,
    )


def test_get_redirection_url_from_state_give_url(mock_redis):
    mixin = set_up_mixin()
    state = "abc"
    mock_redis.set(mixin._get_key_redis(state), "http://localhost/gh/codecov")
    mixin.request.session[mixin._session_key()] = state

    assert mixin.get_redirection_url_from_state("abc") == (
        "http://localhost/gh/codecov",
        True,
    )


def test_remove_state_with_with_delay(mock_redis):
    mixin = set_up_mixin()
    mock_redis.set("oauth-state-abc", "http://localhost/gh/codecov")
    mixin.remove_state("abc", delay=5)
    initial_datetime = datetime.now()
    with freeze_time(initial_datetime) as frozen_time:
        assert mock_redis.get("oauth-state-abc") is not None
        frozen_time.move_to(initial_datetime + timedelta(seconds=4))
        assert mock_redis.get("oauth-state-abc") is not None
        frozen_time.move_to(initial_datetime + timedelta(seconds=6))
        assert mock_redis.get("oauth-state-abc") is None


def test_remove_state_with_with_no_delay(mock_redis):
    mixin = set_up_mixin()
    mock_redis.set("oauth-state-abc", "http://localhost/gh/codecov")
    mixin.remove_state("abc")
    assert mock_redis.get("oauth-state-abc") is None


class LoginMixinTests(TestCase):
    def setUp(self):
        self.mixin_instance = LoginMixin()
        self.mixin_instance.service = "github"
        self.request = RequestFactory().get("", {})
        self.request.user = None
        self.request.current_owner = None
        self.request.session = SessionStore()
        self.mixin_instance.request = self.request

    @patch("services.analytics.AnalyticsService.user_signed_up")
    def test_get_or_create_calls_analytics_user_signed_up_when_owner_created(
        self, user_signed_up_mock
    ):
        self.mixin_instance._get_or_create_owner(
            {
                "user": {"id": 12345, "key": "4567", "login": "testuser"},
                "has_private_access": False,
            },
            self.request,
        )
        user_signed_up_mock.assert_called_once()

    @patch("shared.events.amplitude.AmplitudeEventPublisher.publish")
    def test_get_or_create_calls_amplitude_user_created_when_owner_created(
        self, amplitude_publish_mock
    ):
        self.mixin_instance._get_or_create_owner(
            {
                "user": {"id": 12345, "key": "4567", "login": "testuser"},
                "has_private_access": False,
            },
            self.request,
        )

        owner = Owner.objects.get(service_id=12345, username="testuser")

        amplitude_publish_mock.assert_has_calls(
            [
                call("User Created", {"user_ownerid": owner.ownerid}),
                call("set_orgs", {"user_ownerid": owner.ownerid, "org_ids": []}),
            ]
        )

    @patch("services.analytics.AnalyticsService.user_signed_in")
    def test_get_or_create_calls_analytics_user_signed_in_when_owner_not_created(
        self, user_signed_in_mock
    ):
        owner = OwnerFactory(service_id=89, service="github")
        self.mixin_instance._get_or_create_owner(
            {
                "user": {
                    "id": owner.service_id,
                    "key": "02or0sa",
                    "login": owner.username,
                },
                "has_private_access": owner.private_access,
            },
            self.request,
        )
        user_signed_in_mock.assert_called_once()

    @patch("shared.events.amplitude.AmplitudeEventPublisher.publish")
    def test_get_or_create_calls_amplitude_user_logged_in_when_owner_not_created(
        self, amplitude_publish_mock
    ):
        owner = OwnerFactory(service_id=89, service="github", organizations=[1, 2])
        self.mixin_instance._get_or_create_owner(
            {
                "user": {
                    "id": owner.service_id,
                    "key": "02or0sa",
                    "login": owner.username,
                },
                "has_private_access": owner.private_access,
            },
            self.request,
        )

        amplitude_publish_mock.assert_has_calls(
            [
                call("User Logged in", {"user_ownerid": owner.ownerid}),
                call("set_orgs", {"user_ownerid": owner.ownerid, "org_ids": [1, 2]}),
            ]
        )

    @override_settings(IS_ENTERPRISE=False)
    @patch("services.analytics.AnalyticsService.user_signed_in")
    def test_set_marketing_tags_on_cookies(self, user_signed_in_mock):
        OwnerFactory(service="github")
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

    @override_settings(IS_ENTERPRISE=True)
    def test_get_marketing_tags_on_enterprise(self):
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
        marketing_tags = self.mixin_instance.retrieve_marketing_tags_from_cookie()
        assert marketing_tags == {}

    @patch("services.analytics.AnalyticsService.user_signed_in")
    def test_use_marketing_tags_from_cookies(self, user_signed_in_mock):
        owner = OwnerFactory(service_id=89, service="github")
        self.request.COOKIES["_marketing_tags"] = (
            "utm_department=a&utm_campaign=b&utm_medium=c&utm_source=d&utm_content=e&utm_term=f"
        )
        self.mixin_instance._get_or_create_owner(
            {
                "user": {
                    "id": owner.service_id,
                    "key": "02or0sa",
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

    def mock_get_or_create_owner(self, user_dict, *args):
        owner = OwnerFactory(
            service_id=user_dict.get("id", 89),
            service="github",
        )
        owner.organizations = [1, 2]
        return owner, True

    @override_settings(IS_ENTERPRISE=True)
    @patch(
        "codecov_auth.views.base.LoginMixin._get_or_create_owner",
        mock_get_or_create_owner,
    )
    @patch(
        "codecov_auth.views.base.LoginMixin.get_or_create_org", mock_get_or_create_owner
    )
    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    @patch(
        "codecov_auth.views.base.LoginMixin._check_user_count_limitations",
        lambda *args: True,
    )
    @patch("codecov_auth.views.base.get_config")
    def test_get_and_modify_user_enterprise_raise_usernotinorganization_error(
        self, mock_get_config: Mock
    ):
        user_dict = dict(
            orgs=[],
            is_student=False,
        )
        mock_get_config.return_value = ["awesome-team", "modest_mice"]
        with pytest.raises(PermissionDenied) as exp:
            user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
            self.mixin_instance.login_owner(user, self.request, HttpResponse())
            assert exp.status_code == 401
        mock_get_config.assert_called_with("github", "organizations")

    @patch(
        "codecov_auth.views.base.LoginMixin._get_or_create_owner",
        mock_get_or_create_owner,
    )
    @patch(
        "codecov_auth.views.base.LoginMixin.get_or_create_org", mock_get_or_create_owner
    )
    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    @patch(
        "codecov_auth.views.base.LoginMixin._check_user_count_limitations",
        lambda *args: True,
    )
    @patch("codecov_auth.views.base.get_config")
    @override_settings(IS_ENTERPRISE=True)
    def test_get_and_modify_user_enterprise_orgs_passes_if_user_in_org(
        self, mock_get_config: Mock
    ):
        mock_get_config.return_value = ["awesome-team", "modest_mice"]
        user_dict = dict(
            orgs=[dict(username="awesome-team", id=29)],
            is_student=False,
            user=dict(id=121),
        )
        # This time it should not raise an exception because the user is in one of the orgs
        user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
        self.mixin_instance.login_owner(user, self.request, HttpResponse())
        mock_get_config.assert_any_call("github", "organizations")

    @patch(
        "codecov_auth.views.base.LoginMixin._get_or_create_owner",
        mock_get_or_create_owner,
    )
    @patch(
        "codecov_auth.views.base.LoginMixin.get_or_create_org", mock_get_or_create_owner
    )
    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    @patch(
        "codecov_auth.views.base.LoginMixin._check_user_count_limitations",
        lambda *args: True,
    )
    @patch("codecov_auth.views.base.get_config")
    @override_settings(IS_ENTERPRISE=False)
    def test_get_and_modify_user_passes_if_not_enterprise(self, mock_get_config: Mock):
        user_dict = dict(orgs=[], is_student=False, user=dict(id=121))
        # This time it should not raise an exception because it's not in enterprise mode
        user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
        self.mixin_instance.login_owner(user, self.request, HttpResponse())
        mock_get_config.assert_called_once_with(
            "github", "student_disabled", default=False
        )

    @override_settings(IS_ENTERPRISE=False)
    @patch("codecov_auth.views.base.get_current_license")
    def test_check_user_account_limitations_not_enterprise(
        self, mock_get_current_license: Mock
    ):
        login_data = dict(id=121)
        license = LicenseInformation(
            is_valid=True,
            message=None,
            number_allowed_users=2,
        )
        mock_get_current_license.return_value = license
        self.mixin_instance._check_user_count_limitations(login_data)
        mock_get_current_license.assert_not_called()

    def owner_factory_side_effect(self, serivce_id, token):
        owner = OwnerFactory(serivce_id=serivce_id, service="github")
        owner.oauth_token = token
        return owner

    @override_settings(IS_ENTERPRISE=True)
    @patch("codecov_auth.models.Owner.objects")
    @patch("codecov_auth.views.base.get_current_license")
    def test_check_user_account_limitations_enterprise_user_exists_not_pr_billing(
        self, mock_get_current_license: Mock, mock_owner_objects: Mock
    ):
        login_data = dict(id=121)
        license = LicenseInformation(
            is_valid=True, message=None, number_allowed_users=2, is_pr_billing=False
        )
        mock_get_current_license.return_value = license
        mock_owner_objects.get.return_value = self.owner_factory_side_effect(
            1200, token="somethingsomething"
        )
        self.mixin_instance._check_user_count_limitations(login_data)
        mock_get_current_license.assert_called_once()
        mock_owner_objects.get.assert_called_once()

    @override_settings(IS_ENTERPRISE=True)
    @patch("codecov_auth.views.base.get_current_license")
    def test_check_user_account_limitations_enterprise_user_new_not_pr_billing(
        self, mock_get_current_license: Mock
    ):
        login_data = dict(id=121)
        license = LicenseInformation(
            is_valid=True, message=None, number_allowed_users=1, is_pr_billing=False
        )
        mock_get_current_license.return_value = license
        # If the number of users is smaller than the limit, no exception is raised
        # In this case
        self.mixin_instance._check_user_count_limitations(login_data)
        mock_get_current_license.assert_called_once()
        assert (
            Owner.objects.filter(oauth_token__isnull=False, service="github").count()
            == 0
        )
        # If the number of users is larger than the limit, raise error
        with pytest.raises(PermissionDenied):
            OwnerFactory(service="github", ownerid=12, oauth_token="very-fake-token")
            OwnerFactory(service="github", ownerid=13, oauth_token=None)
            OwnerFactory(service="github", ownerid=14, oauth_token="very-fake-token")
            assert (
                Owner.objects.filter(
                    oauth_token__isnull=False, service="github"
                ).count()
                == 2
            )
            self.mixin_instance._check_user_count_limitations(login_data)
            mock_get_current_license.assert_called()

    @override_settings(IS_ENTERPRISE=True)
    @patch("codecov_auth.views.base.get_current_license")
    def test_check_user_account_limitations_enterprise_pr_billing(
        self, mock_get_current_license: Mock
    ):
        license = LicenseInformation(
            is_valid=True, message=None, number_allowed_users=1, is_pr_billing=True
        )
        mock_get_current_license.return_value = license
        # User doesn't exist, and existing users will raise error
        with pytest.raises(PermissionDenied):
            OwnerFactory(ownerid=1, service="github", plan_activated_users=[1, 2, 3])
            OwnerFactory(
                ownerid=2,
                service="github",
                service_id="batata_frita",
                plan_activated_users=[],
            )
            OwnerFactory(ownerid=3, service="github", plan_activated_users=None)
            assert (
                Owner.objects.exclude(plan_activated_users__len=0)
                .exclude(plan_activated_users__isnull=True)
                .count()
                == 1
            )
            assert Owner.objects.exclude(plan_activated_users__len=0)[
                0
            ].plan_activated_users == [1, 2, 3]
            self.mixin_instance._check_user_count_limitations(dict(id=121))
            mock_get_current_license.assert_called()
        # If user exists, don't raise exception
        assert (
            Owner.objects.get(service="github", service_id="batata_frita").ownerid == 2
        )
        self.mixin_instance._check_user_count_limitations(dict(id="batata_frita"))

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    @patch(
        "codecov_auth.views.base.LoginMixin._check_user_count_limitations",
        lambda *args: True,
    )
    @patch(
        "codecov_auth.views.base.LoginMixin._get_or_create_owner",
        mock_get_or_create_owner,
    )
    @patch("codecov_auth.views.base.get_config")
    def test_github_teams_restrictions(self, mock_get_config: Mock):
        def side_effect(*args, **kwargs):
            if len(args) == 2 and args[0] == "github" and args[1] == "organizations":
                return ["my-org"]
            if len(args) == 2 and args[0] == "github" and args[1] == "teams":
                return ["My Team"]
            if len(args) == 2 and args[0] == "github" and args[1] == "student_disabled":
                return False

        mock_get_config.side_effect = side_effect
        user_dict = dict(
            orgs=[dict(username="my-org", id=29)],
            is_student=False,
            user=dict(id=121, login="something"),
            teams=[],
        )
        # Raise exception because user is not member of My Team
        with pytest.raises(PermissionDenied) as exp:
            user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
            self.mixin_instance.login_owner(user, self.request, HttpResponse())
            mock_get_config.assert_any_call("github", "organizations")
            mock_get_config.assert_any_call("github", "teams")
            assert (
                str(exp)
                == "You must be a member of an allowed team in your organization."
            )
            assert exp.status_code == 401
        # No exception if user is in My Team
        user_dict["teams"] = [dict(name="My Team")]
        user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
        self.mixin_instance.login_owner(user, self.request, HttpResponse())
        mock_get_config.assert_any_call("github", "organizations")
        mock_get_config.assert_any_call("github", "teams")
        mock_get_config.assert_any_call("github", "student_disabled", default=False)

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    @patch(
        "codecov_auth.views.base.LoginMixin._check_user_count_limitations",
        lambda *args: True,
    )
    @patch(
        "codecov_auth.views.base.LoginMixin._get_or_create_owner",
        mock_get_or_create_owner,
    )
    @patch("codecov_auth.views.base.get_config")
    def test_github_teams_restrictions_no_teams_in_config(self, mock_get_config: Mock):
        def side_effect(*args, **kwargs):
            if len(args) == 2 and args[0] == "github" and args[1] == "organizations":
                return ["my-org"]
            if len(args) == 2 and args[0] == "github" and args[1] == "teams":
                return []
            if len(args) == 2 and args[0] == "github" and args[1] == "student_disabled":
                return False

        mock_get_config.side_effect = side_effect
        user_dict = dict(
            orgs=[dict(username="my-org", id=29)],
            is_student=False,
            user=dict(id=121, login="something"),
            teams=[dict(name="My Team")],
        )
        # Don't raise exception if there's no team in the config
        user = self.mixin_instance.get_and_modify_owner(user_dict, self.request)
        self.mixin_instance.login_owner(user, self.request, HttpResponse())
        mock_get_config.assert_any_call("github", "organizations")
        mock_get_config.assert_any_call("github", "teams")
        mock_get_config.assert_any_call("github", "student_disabled", default=False)

    def test_adjust_redirection_url_is_unchanged_if_url_is_different_from_base_url(
        self,
    ):
        provider = "gh"
        owner = OwnerFactory(
            username="sample-owner",
            service="github",
        )
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}/some/random/path/to/file.py"

        redirect_url = (
            self.mixin_instance.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url

    def test_adjust_redirection_url_is_unchanged_if_no_owner_profile(self):
        provider = "gh"
        owner = OwnerFactory(
            username="sample-owner",
            service="github",
        )
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        redirect_url = (
            self.mixin_instance.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url

    def test_adjust_redirection_url_is_unchanged_if_no_default_org(self):
        provider = "gh"
        owner = OwnerFactory(
            username="sample-owner-gh",
            service="github",
        )
        # OwnerProfile implicitly has no default org
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        redirect_url = (
            self.mixin_instance.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url

    def test_adjust_redirection_url_user_has_a_default_org_for_github(self):
        provider = "gh"
        default_org_username = "sample-org-gh"
        organization = OwnerFactory(username=default_org_username, service="github")
        owner = OwnerFactory(
            username="sample-owner-gh",
            service="github",
            organizations=[organization.ownerid],
        )
        OwnerProfile.objects.filter(owner_id=owner.ownerid).update(
            default_org=organization
        )
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        redirect_url = (
            self.mixin_instance.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url + f"/{default_org_username}"

    def test_adjust_redirection_url_user_has_a_default_org_for_gitlab(self):
        provider = "gl"
        default_org_username = "sample-org-gl"
        organization = OwnerFactory(username=default_org_username, service="gitlab")
        owner = OwnerFactory(
            username="sample-owner-gl",
            service="gitlab",
            organizations=[organization.ownerid],
        )
        OwnerProfile.objects.filter(owner_id=owner.ownerid).update(
            default_org=organization
        )
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        mixin_instance_gitlab = LoginMixin()
        mixin_instance_gitlab.service = "gitlab"

        redirect_url = (
            mixin_instance_gitlab.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url + f"/{default_org_username}"

    def test_adjust_redirection_url_user_has_a_default_org_for_bitbucket(self):
        provider = "bb"
        default_org_username = "sample-org-bb"
        organization = OwnerFactory(username=default_org_username, service="bitbucket")
        owner = OwnerFactory(
            username="sample-owner-bb",
            service="bitbucket",
            organizations=[organization.ownerid],
        )
        OwnerProfile.objects.filter(owner_id=owner.ownerid).update(
            default_org=organization
        )
        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        mixin_instance_bitbucket = LoginMixin()
        mixin_instance_bitbucket.service = "bitbucket"

        redirect_url = (
            mixin_instance_bitbucket.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url + f"/{default_org_username}"

    def test_adjust_redirection_url_user_has_a_default_org_for_github_long_org_name(
        self,
    ):
        provider = "github"
        default_org_username = "sample-org-gh"
        organization = OwnerFactory(username=default_org_username, service="github")
        owner = OwnerFactory(
            username="sample-owner-gh",
            service="github",
            organizations=[organization.ownerid],
        )
        # OwnerProfiles get created automatically, so we need to fetch and update the entry manually
        OwnerProfile.objects.filter(owner_id=owner.ownerid).update(
            default_org=organization
        )

        url = f"{settings.CODECOV_DASHBOARD_URL}/{provider}"

        redirect_url = (
            self.mixin_instance.modify_redirection_url_based_on_default_user_org(
                url, owner
            )
        )
        assert redirect_url == url + f"/{default_org_username}"

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_unauthenticated_with_claimed_owner(self):
        self.request.user = None
        owner = OwnerFactory()
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        assert self.request.user == owner.user

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_unauthenticated_with_unclaimed_owner(self):
        self.request.user = None
        owner = OwnerFactory(user=None)
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        # creates new user
        assert self.request.user == owner.user
        assert self.request.user.email == owner.email
        assert self.request.user.name == owner.name

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_authenticated_with_unclaimed_owner(self):
        user = UserFactory()
        owner = OwnerFactory(user=None)
        self.request.user = user
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        owner.refresh_from_db()
        assert owner.user == user

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_authenticated_with_existing_service_owner(self):
        user = UserFactory()
        OwnerFactory(service="github", user=user)
        owner = OwnerFactory(user=None, service="github")
        self.request.user = user
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        owner.refresh_from_db()

        # logs in new user
        assert self.request.user is not None
        assert self.request.user != user

        # and claims owner w/ that new user
        assert owner.user is not None
        assert owner.user != user

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_authenticated_with_claimed_owner(self):
        user = UserFactory()
        owner = OwnerFactory(service="github")
        self.request.user = user
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        owner.refresh_from_db()

        assert self.request.user == owner.user

        # does not re-claim owner
        assert owner.user is not None
        assert owner.user != user

    @patch("services.refresh.RefreshService.trigger_refresh", lambda *args: None)
    def test_login_owner_with_expired_login_session(self):
        user = UserFactory()
        owner = OwnerFactory(service="github", user=user)

        another_user = UserFactory()
        another_owner = OwnerFactory(service="github", user=another_user)

        now = datetime.now(timezone.utc)

        # Create a session that will be deleted
        to_be_deleted_1 = SessionFactory(
            owner=owner,
            type="login",
            name="to_be_deleted",
            lastseen="2021-01-01T00:00:00+00:00",
            login_session=DjangoSessionFactory(expire_date=now - timedelta(days=1)),
        )
        to_be_deleted_1_session_key = to_be_deleted_1.login_session.session_key

        # Create a session that will not be deleted because its not a login session
        to_be_kept_1 = SessionFactory(
            owner=owner,
            type="api",
            name="to_be_kept",
            lastseen="2021-01-01T00:00:00+00:00",
            login_session=DjangoSessionFactory(expire_date=now + timedelta(days=1)),
        )

        # Create a session that will not be deleted because it's not expired
        to_be_kept_2 = SessionFactory(
            owner=owner,
            type="login",
            name="to_be_kept",
            lastseen="2021-01-01T00:00:00+00:00",
            login_session=DjangoSessionFactory(expire_date=now + timedelta(days=1)),
        )

        # Create a session that will not be deleted because it's not the owner's session
        to_be_kept_3 = SessionFactory(
            owner=another_owner,
            type="login",
            name="to_be_kept",
            lastseen="2021-01-01T00:00:00+00:00",
            login_session=DjangoSessionFactory(expire_date=now - timedelta(seconds=1)),
        )

        assert (
            len(DjangoSession.objects.filter(session_key=to_be_deleted_1_session_key))
            == 1
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_1.login_session.session_key
                )
            )
            == 1
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_2.login_session.session_key
                )
            )
            == 1
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_3.login_session.session_key
                )
            )
            == 1
        )

        self.request.user = user
        self.mixin_instance.login_owner(owner, self.request, HttpResponse())
        owner.refresh_from_db()

        new_login_session = Session.objects.filter(name=None)

        assert len(new_login_session) == 1
        assert len(Session.objects.filter(name="to_be_deleted").all()) == 0
        assert len(Session.objects.filter(name="to_be_kept").all()) == 3

        assert (
            len(DjangoSession.objects.filter(session_key=to_be_deleted_1_session_key))
            == 0
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_1.login_session.session_key
                )
            )
            == 1
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_2.login_session.session_key
                )
            )
            == 1
        )
        assert (
            len(
                DjangoSession.objects.filter(
                    session_key=to_be_kept_3.login_session.session_key
                )
            )
            == 1
        )
