from datetime import datetime
from unittest.mock import call, patch

import pytest
from django.test import TestCase

from codecov_auth.models import PlanProviders
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from services.segment import (
    BLANK_SEGMENT_USER_ID,
    SegmentEvent,
    SegmentOwner,
    SegmentRepository,
    SegmentService,
    on_segment_error,
)


class SegmentOwnerTests(TestCase):
    def setUp(self):
        self.segment_owner = SegmentOwner(
            OwnerFactory(
                private_access=True,
                plan_provider=PlanProviders.GITHUB.value,
                plan_user_count=10,
                delinquent=True,
                did_trial=True,
                student=True,
                bot=OwnerFactory(),
                email="user@codecov.io",
                student_created_at=datetime(2017, 1, 1, 12, 0, 0, 5000),
                student_updated_at=datetime(2018, 1, 1, 12, 0, 0, 5000),
            )
        )

    def test_traits(self):
        expected_traits = {
            "email": self.segment_owner.owner.email,
            "name": self.segment_owner.owner.name,
            "username": self.segment_owner.owner.username,
            "avatar": self.segment_owner.owner.avatar_url,
            "createdAt": datetime(2014, 1, 1, 12, 0, 0),
            "updatedAt": self.segment_owner.owner.updatestamp.replace(microsecond=0),
            "service": self.segment_owner.owner.service,
            "service_id": self.segment_owner.owner.service_id,
            "private_access": self.segment_owner.owner.private_access,
            "plan": self.segment_owner.owner.plan,
            "plan_provider": self.segment_owner.owner.plan_provider,
            "plan_user_count": self.segment_owner.owner.plan_user_count,
            "delinquent": self.segment_owner.owner.delinquent,
            "did_trial": self.segment_owner.owner.did_trial,
            "student": self.segment_owner.owner.student,
            "student_created_at": datetime(2017, 1, 1, 12, 0, 0),
            "student_updated_at": datetime(2018, 1, 1, 12, 0, 0),
            "staff": self.segment_owner.owner.staff,
            "bot": self.segment_owner.owner.bot,
            "has_yaml": self.segment_owner.owner.yaml is not None,
        }

        assert self.segment_owner.traits == expected_traits

    @pytest.mark.skip
    def test_traits_defaults(self):
        segment_owner_missing_traits = SegmentOwner(
            OwnerFactory(
                email=None,
                name=None,
                username=None,
                private_access=None,
                plan_provider=None,
                plan_user_count=None,
                delinquent=None,
                did_trial=None,
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
            "avatar": segment_owner_missing_traits.owner.avatar_url,
            "createdAt": datetime(2014, 1, 1, 12, 0, 0),
            "updatedAt": self.segment_owner.owner.updatestamp.replace(microsecond=0),
            "service": segment_owner_missing_traits.owner.service,
            "service_id": segment_owner_missing_traits.owner.service_id,
            "private_access": False,
            "plan": segment_owner_missing_traits.owner.plan,
            "plan_provider": "",
            "plan_user_count": 5,
            "delinquent": False,
            "did_trial": False,
            "student": False,
            "student_created_at": datetime(2014, 1, 1, 12, 0, 0),
            "student_updated_at": datetime(2014, 1, 1, 12, 0, 0),
            "staff": segment_owner_missing_traits.owner.staff,
            "bot": False,
            "has_yaml": segment_owner_missing_traits.owner.yaml is not None,
        }

        assert segment_owner_missing_traits.traits == expected_traits

    def test_context(self):
        marketo_cookie, ga_cookie = "foo", "GA1.2.1429057651.1605972584"
        cookies = {"_mkto_trk": marketo_cookie, "_ga": ga_cookie}

        self.segment_owner = SegmentOwner(
            OwnerFactory(stripe_customer_id=684), cookies=cookies
        )

        expected_context = {
            "externalIds": [
                {
                    "id": self.segment_owner.owner.service_id,
                    "type": f"{self.segment_owner.owner.service}_id",
                    "collection": "users",
                    "encoding": "none",
                },
                {
                    "id": self.segment_owner.owner.stripe_customer_id,
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

        assert self.segment_owner.context == expected_context


class SegmentServiceTests(TestCase):
    def setUp(self):
        self.segment_service = SegmentService()
        self.owner = OwnerFactory()
        self.segment_owner = SegmentOwner(self.owner)

    def test_on_segment_error_doesnt_crash(self):
        on_segment_error(Exception())

    @patch("analytics.identify")
    def test_identify_user(self, identify_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.identify_user(self.owner)
            identify_mock.assert_called_once_with(
                self.segment_owner.user_id,
                self.segment_owner.traits,
                self.segment_owner.context,
                integrations={"Salesforce": True, "Marketo": False},
            )

    @patch("analytics.track")
    def test_user_signed_up(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            expected_event_properties = {
                **self.segment_owner.traits,
                "signup_department": "marketing",
                "signup_campaign": "",
                "signup_medium": "",
                "signup_source": "direct",
                "signup_content": "",
                "signup_term": "",
            }
            self.segment_service.user_signed_up(self.owner)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_UP.value,
                expected_event_properties,
            )

    @patch("analytics.track")
    def test_user_signed_in(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            tracking_params = {
                "utm_department": "sales",
                "utm_campaign": "campaign",
                "utm_medium": "medium",
                "utm_source": "source",
                "utm_content": "content",
                "utm_term": "term",
            }
            expected_event_properties = {
                **self.segment_owner.traits,
                "signup_department": "sales",
                "signup_campaign": "campaign",
                "signup_medium": "medium",
                "signup_source": "source",
                "signup_content": "content",
                "signup_term": "term",
            }
            self.segment_service.user_signed_in(self.owner, **tracking_params)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_IN.value,
                expected_event_properties,
            )

    @patch("analytics.track")
    def test_user_signed_out(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.user_signed_out(self.owner)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_OUT.value,
                self.segment_owner.traits,
            )

    @patch("analytics.track")
    def test_account_activated_user(self, track_mock):
        owner_to_activate = OwnerFactory()
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_activated_user(
                current_user_ownerid=self.owner.ownerid,
                ownerid_to_activate=owner_to_activate.ownerid,
                org_ownerid=org.ownerid,
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_ACTIVATED_USER.value,
                properties={
                    "role": "admin",
                    "user": owner_to_activate.ownerid,
                    "auto_activated": False,
                },
                context={"groupId": org.ownerid},
            )

    @patch("analytics.track")
    def test_account_deactivated_user(self, track_mock):
        owner_to_deactivate = OwnerFactory()
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_deactivated_user(
                current_user_ownerid=self.owner.ownerid,
                ownerid_to_deactivate=owner_to_deactivate.ownerid,
                org_ownerid=org.ownerid,
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_DEACTIVATED_USER.value,
                properties={"role": "admin", "user": owner_to_deactivate.ownerid,},
                context={"groupId": org.ownerid},
            )

    @patch("analytics.track")
    def test_account_increased_users(self, track_mock):
        plan_details = {"old_quantity": 2, "new_quantity": 3, "plan": "users-inappm"}
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_increased_users(
                current_user_ownerid=self.owner.ownerid,
                org_ownerid=org.ownerid,
                plan_details=plan_details,
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_INCREASED_USERS.value,
                properties=plan_details,
                context={"groupId": org.ownerid},
            )

    @patch("analytics.track")
    def test_account_decreased_users(self, track_mock):
        plan_details = {"old_quantity": 3, "new_quantity": 2, "plan": "users-inappm"}
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_decreased_users(
                current_user_ownerid=self.owner.ownerid,
                org_ownerid=org.ownerid,
                plan_details=plan_details,
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_DECREASED_USERS.value,
                properties=plan_details,
                context={"groupId": org.ownerid},
            )

    @patch("analytics.track")
    def test_account_deleted(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_deleted(self.owner)
            track_mock.assert_called_with(
                user_id=self.segment_owner.user_id,
                properties=self.segment_owner.traits,
                context={"groupId": self.owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_activated_repository(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_activated_repository(
                owner.ownerid, repo,
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_ACTIVATED_REPOSITORY.value,
                properties=SegmentRepository(repo).traits,
                context={"groupId": repo.author.ownerid},
            )

    @patch("analytics.track")
    def test_account_deactivated_repository(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_deactivated_repository(
                owner.ownerid, repo,
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_DEACTIVATED_REPOSITORY.value,
                properties=SegmentRepository(repo).traits,
                context={"groupId": repo.author.ownerid},
            )

    @patch("analytics.track")
    def test_account_erased_repository(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_erased_repository(
                owner.ownerid, repo,
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_ERASED_REPOSITORY.value,
                properties=SegmentRepository(repo).traits,
                context={"groupId": repo.author.ownerid},
            )

    @patch("analytics.track")
    def test_account_deleted_repository(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_deleted_repository(
                owner.ownerid, repo,
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_DELETED_REPOSITORY.value,
                properties=SegmentRepository(repo).traits,
                context={"groupId": repo.author.ownerid},
            )

    @patch("analytics.track")
    def test_account_activated_repository_on_upload(self, track_mock):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_activated_repository_on_upload(
                owner.ownerid, repo,
            )
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.ACCOUNT_ACTIVATED_REPOSITORY_ON_UPLOAD.value,
                properties=SegmentRepository(repo).traits,
                context={"groupId": repo.author.ownerid},
            )

    @patch("analytics.track")
    def test_account_paid_subscription(self, track_mock):
        owner = OwnerFactory(plan="users-inappm")
        stripe_subscription_details = {"plan": owner.plan}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_paid_subscription(
                owner.ownerid, stripe_subscription_details
            )
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.ACCOUNT_PAID_SUBSCRIPTION.value,
                properties=stripe_subscription_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_cancelled_subscription(self, track_mock):
        owner = OwnerFactory(plan="users-inappm")
        stripe_subscription_details = {"plan": owner.plan}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_cancelled_subscription(
                owner.ownerid, stripe_subscription_details
            )
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.ACCOUNT_CANCELLED_SUBSCRIPTION.value,
                properties=stripe_subscription_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_changed_plan(self, track_mock):
        owner = OwnerFactory(plan="users-inappm")
        plan_change_details = {"new_plan": "users_free", "previous_plan": owner.plan}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_changed_plan(
                self.owner.ownerid, owner.ownerid, plan_change_details
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_CHANGED_PLAN.value,
                properties=plan_change_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_trial_started(self, track_mock):
        owner = OwnerFactory()
        trial_details = {"some": "data"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.trial_started(owner.ownerid, trial_details)
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.TRIAL_STARTED.value,
                properties=trial_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_trial_ended(self, track_mock):
        owner = OwnerFactory()
        trial_details = {"some": "data"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.trial_ended(owner.ownerid, trial_details)
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.TRIAL_ENDED.value,
                properties=trial_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_completed_checkout(self, track_mock):
        owner = OwnerFactory()
        stripe_subscription_details = {"plan": owner.plan, "userid_type": "org"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_completed_checkout(
                owner.ownerid, stripe_subscription_details
            )
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.ACCOUNT_COMPLETED_CHECKOUT.value,
                properties=stripe_subscription_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.group")
    def test_group(self, group_mock):
        org1, org2 = OwnerFactory(), OwnerFactory()
        self.owner.organizations = [org1.ownerid, org2.ownerid]
        self.owner.save()

        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.group(self.owner)
            group_mock.assert_has_calls(
                [
                    call(
                        user_id=self.owner.ownerid,
                        group_id=org1.ownerid,
                        traits=SegmentOwner(
                            org1, owner_collection_type="accounts"
                        ).traits,
                        context=SegmentOwner(
                            org1, owner_collection_type="accounts"
                        ).context,
                    ),
                    call(
                        user_id=self.owner.ownerid,
                        group_id=org2.ownerid,
                        traits=SegmentOwner(
                            org2, owner_collection_type="accounts"
                        ).traits,
                        context=SegmentOwner(
                            org2, owner_collection_type="accounts"
                        ).context,
                    ),
                ]
            )

    @patch("analytics.track")
    def test_account_installed_source_control_service_app(self, track_mock):
        owner = OwnerFactory()
        app_details = {"platform": "github"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_installed_source_control_service_app(
                owner.ownerid, owner.ownerid, app_details
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_INSTALLED_SOURCE_CONTROL_APP.value,
                properties=app_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_uninstalled_source_control_service_app(self, track_mock):
        owner = OwnerFactory()
        app_details = {"platform": "github"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_uninstalled_source_control_service_app(
                owner.ownerid, owner.ownerid, app_details
            )
            track_mock.assert_called_once_with(
                user_id=owner.ownerid,
                event=SegmentEvent.ACCOUNT_UNINSTALLED_SOURCE_CONTROL_APP.value,
                properties=app_details,
                context={"groupId": owner.ownerid},
            )

    @patch("analytics.track")
    def test_account_uploaded_coverage_report(self, track_mock):
        owner = OwnerFactory()
        upload_details = {"some": "dict"}
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_uploaded_coverage_report(
                owner.ownerid, upload_details
            )
            track_mock.assert_called_once_with(
                user_id=BLANK_SEGMENT_USER_ID,
                event=SegmentEvent.ACCOUNT_UPLOADED_COVERAGE_REPORT.value,
                properties=upload_details,
                context={"groupId": owner.ownerid},
            )
