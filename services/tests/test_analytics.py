from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone
from shared.analytics_tracking.events import Events
from shared.django_apps.codecov_auth.tests.factories import UserFactory
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov_auth.models import PlanProviders
from services.analytics import AnalyticsOwner, AnalyticsRepository, AnalyticsService


class AnalyticsOwnerTests(TestCase):
    def setUp(self):
        self.analytics_owner = AnalyticsOwner(
            OwnerFactory(
                private_access=True,
                plan_provider=PlanProviders.GITHUB.value,
                plan_user_count=10,
                delinquent=True,
                trial_start_date=timezone.now(),
                trial_end_date=timezone.now() + timedelta(days=14),
                student=True,
                bot=OwnerFactory(),
                email="user@codecov.io",
                student_created_at=datetime(2017, 1, 1, 12, 0, 0, 5000),
                student_updated_at=datetime(2018, 1, 1, 12, 0, 0, 5000),
            )
        )

    def test_traits(self):
        expected_traits = {
            "email": self.analytics_owner.owner.email,
            "username": self.analytics_owner.owner.username,
            "service": self.analytics_owner.owner.service,
            "service_id": self.analytics_owner.owner.service_id,
            "plan": self.analytics_owner.owner.plan,
            "owner_id": self.analytics_owner.owner.ownerid,
            "user_id": self.analytics_owner.owner.ownerid,
        }

        assert self.analytics_owner.traits == expected_traits

    @pytest.mark.skip
    def test_traits_defaults(self):
        analytics_owner_missing_traits = AnalyticsOwner(
            OwnerFactory(
                email=None,
                name=None,
                username=None,
                private_access=None,
                plan_provider=None,
                plan_user_count=None,
                delinquent=None,
                trial_start_date=None,
                trial_end_date=None,
                student=0,
                bot=None,
                student_created_at=None,
                student_updated_at=None,
            )
        )

        expected_traits = {
            "email": "unknown@codecov.io",
            "name": "unknown",
            "username": "unknown",
            "avatar": analytics_owner_missing_traits.owner.avatar_url,
            "createdAt": datetime(2014, 1, 1, 12, 0, 0),
            "updatedAt": self.analytics_owner.owner.updatestamp.replace(microsecond=0),
            "service": analytics_owner_missing_traits.owner.service,
            "service_id": analytics_owner_missing_traits.owner.service_id,
            "private_access": False,
            "plan": analytics_owner_missing_traits.owner.plan,
            "plan_provider": "",
            "plan_user_count": 5,
            "delinquent": False,
            "trial_start_date": None,
            "trial_end_date": None,
            "student": False,
            "student_created_at": datetime(2014, 1, 1, 12, 0, 0),
            "student_updated_at": datetime(2014, 1, 1, 12, 0, 0),
            "staff": analytics_owner_missing_traits.owner.staff,
            "bot": False,
            "has_yaml": analytics_owner_missing_traits.owner.yaml is not None,
        }

        assert analytics_owner_missing_traits.traits == expected_traits

    def test_context(self):
        marketo_cookie, ga_cookie = "foo", "GA1.2.1429057651.1605972584"
        cookies = {"_mkto_trk": marketo_cookie, "_ga": ga_cookie}

        self.analytics_owner = AnalyticsOwner(
            OwnerFactory(stripe_customer_id=684), cookies=cookies
        )

        expected_context = {
            "externalIds": [
                {
                    "id": self.analytics_owner.owner.service_id,
                    "type": f"{self.analytics_owner.owner.service}_id",
                    "collection": "users",
                    "encoding": "none",
                },
                {
                    "id": self.analytics_owner.owner.stripe_customer_id,
                    "type": "stripe_customer_id",
                    "collection": "users",
                    "encoding": "none",
                },
                {
                    "id": marketo_cookie,
                    "type": "marketo_cookie",
                    "collection": "users",
                    "encoding": "none",
                },
                {
                    "id": "1429057651.1605972584",
                    "type": "ga_client_id",
                    "collection": "users",
                    "encoding": "none",
                },
            ],
            "Marketo": {"marketo_cookie": marketo_cookie},
        }

        assert self.analytics_owner.context == expected_context


class AnalyticsServiceTests(TestCase):
    def setUp(self):
        self.analytics_service = AnalyticsService()
        self.owner = OwnerFactory()
        self.analytics_owner = AnalyticsOwner(self.owner)

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_user_signed_up(self, track_mock):
        with self.settings(IS_ENTERPRISE=True):
            self.analytics_service.user_signed_up(self.owner)
            track_mock.assert_called_once_with(
                Events.USER_SIGNED_UP.value,
                is_enterprise=True,
                event_data=self.analytics_owner.traits,
            )

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_user_signed_in(self, track_mock):
        with self.settings(IS_ENTERPRISE=False):
            self.analytics_service.user_signed_in(self.owner)
            track_mock.assert_called_once_with(
                Events.USER_SIGNED_IN.value,
                is_enterprise=False,
                event_data=self.analytics_owner.traits,
            )

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_account_activated_repository(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(IS_ENTERPRISE=False):
            self.analytics_service.account_activated_repository(owner.ownerid, repo)
            event_data = {
                **AnalyticsRepository(repo).traits,
                "user_id": owner.ownerid,
            }
            track_mock.assert_called_once_with(
                Events.ACCOUNT_ACTIVATED_REPOSITORY.value,
                is_enterprise=False,
                event_data=event_data,
                context={"groupId": repo.author.ownerid},
            )

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_account_activated_repository_on_upload(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(IS_ENTERPRISE=False):
            self.analytics_service.account_activated_repository_on_upload(
                owner.ownerid, repo
            )
            track_mock.assert_called_once_with(
                Events.ACCOUNT_ACTIVATED_REPOSITORY_ON_UPLOAD.value,
                is_enterprise=False,
                event_data={
                    **AnalyticsRepository(repo).traits,
                    "user_id": owner.ownerid,
                },
                context={"groupId": repo.author.ownerid},
            )

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_account_uploaded_coverage_report(self, track_mock):
        owner = OwnerFactory()
        upload_details = {"some": "dict", "user_id": owner.ownerid}
        with self.settings(IS_ENTERPRISE=False):
            self.analytics_service.account_uploaded_coverage_report(
                owner.ownerid, upload_details
            )
            track_mock.assert_called_once_with(
                Events.ACCOUNT_UPLOADED_COVERAGE_REPORT.value,
                is_enterprise=False,
                event_data=upload_details,
                context={"groupId": owner.ownerid},
            )

    @patch("shared.analytics_tracking.analytics_manager.track_event")
    def test_opt_in_email(self, track_mock):
        user = UserFactory()
        data = {
            "email": user.email,
        }

        with self.settings(IS_ENTERPRISE=False):
            self.analytics_service.opt_in_email(user.id, data)
            track_mock.assert_called_once_with(
                Events.GDPR_OPT_IN.value,
                is_enterprise=False,
                event_data={**data, "user_id": user.id},
            )
