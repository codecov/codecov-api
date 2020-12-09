from django.test import TestCase
from codecov_auth.tests.factories import OwnerFactory

from services.segment import SegmentOwner, SegmentService, SegmentEvent, on_segment_error
from unittest.mock import patch


class SegmentOwnerTests(TestCase):
    def setUp(self):
        self.segment_owner = SegmentOwner(OwnerFactory())

    def test_traits(self):
        expected_traits = {
            'email': self.segment_owner.owner.email, 
            'name': self.segment_owner.owner.name,
            'username': self.segment_owner.owner.username,
            'avatar': self.segment_owner.owner.avatar_url,
            'createdAt': self.segment_owner.owner.createstamp,
            'updatedAt': self.segment_owner.owner.updatestamp,
            'service': self.segment_owner.owner.service,
            'service_id': self.segment_owner.owner.service_id,
            'private_access': self.segment_owner.owner.private_access,
            'plan': self.segment_owner.owner.plan,
            'plan_provider': self.segment_owner.owner.plan_provider,
            'plan_user_count': self.segment_owner.owner.plan_user_count,
            'delinquent': self.segment_owner.owner.delinquent,
            'did_trial': self.segment_owner.owner.did_trial,
            'student': self.segment_owner.owner.student,
            'student_created_at': self.segment_owner.owner.student_created_at,
            'student_updated_at': self.segment_owner.owner.student_updated_at,
            'staff': self.segment_owner.owner.staff,
            'bot': self.segment_owner.owner.bot,
            'has_yaml': self.segment_owner.owner.yaml is not None,
        }

        assert self.segment_owner.traits == expected_traits

    def test_context(self):
        marketo_cookie, ga_cookie = "foo", "GA1.2.1429057651.1605972584"
        cookies = {
            "_mkto_trk": marketo_cookie,
            "_ga": ga_cookie
        }

        self.segment_owner = SegmentOwner(OwnerFactory(stripe_customer_id=684), cookies=cookies)

        expected_context = {
            "externalIds": [
                {
                    "id": self.segment_owner.owner.service_id,
                    "type": f"{self.segment_owner.owner.service}_id",
                    "collection": "users",
                    "encoding": "none"
                },
                {
                    "id": self.segment_owner.owner.stripe_customer_id,
                    "type": "stripe_customer_id",
                    "collection": "users",
                    "encoding": "none"
                },
                {
                    "id": marketo_cookie,
                    "type": "marketo_cookie",
                    "collection": "users",
                    "encoding": "none"
                },
                {
                    "id": "1429057651.1605972584",
                    "type": "ga_client_id",
                    "collection": "users",
                    "encoding": "none"
                },
            ],
            "Marketo": {"marketo_cookie": marketo_cookie}
        }

        assert self.segment_owner.context == expected_context


class SegmentServiceTests(TestCase):
    def setUp(self):
        self.segment_service = SegmentService()
        self.owner = OwnerFactory()
        self.segment_owner = SegmentOwner(self.owner)

    def test_on_segment_error_doesnt_crash(self):
        on_segment_error(Exception())

    @patch('analytics.identify')
    def test_identify_user(self, identify_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.identify_user(self.owner)
            identify_mock.assert_called_once_with(
                self.segment_owner.user_id,
                self.segment_owner.traits,
                self.segment_owner.context,
                integrations={
                    "Salesforce": False,
                    "Marketo": False
                }
            )

    @patch('analytics.track')
    def test_user_signed_up(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.user_signed_up(self.owner)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_UP.value,
                self.segment_owner.traits
            )

    @patch('analytics.track')
    def test_user_signed_in(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.user_signed_in(self.owner)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_IN.value,
                self.segment_owner.traits
            )

    @patch('analytics.track')
    def test_user_signed_out(self, track_mock):
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.user_signed_out(self.owner)
            track_mock.assert_called_once_with(
                self.segment_owner.user_id,
                SegmentEvent.USER_SIGNED_OUT.value,
                self.segment_owner.traits
            )

    @patch('analytics.track')
    def test_account_activated_user(self, track_mock):
        owner_to_activate = OwnerFactory()
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_activated_user(
                current_user_ownerid=self.owner.ownerid,
                ownerid_to_activate=owner_to_activate.ownerid,
                org_ownerid=org.ownerid
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_ACTIVATED_USER.value,
                properties={
                    "role": "admin",
                    "user": owner_to_activate.ownerid,
                    "auto_activated": False 
                },
                context={"groupId": org.ownerid}
            )

    @patch('analytics.track')
    def test_account_deactivated_user(self, track_mock):
        owner_to_deactivate = OwnerFactory()
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_deactivated_user(
                current_user_ownerid=self.owner.ownerid,
                ownerid_to_deactivate=owner_to_deactivate.ownerid,
                org_ownerid=org.ownerid
            )
            track_mock.assert_called_once_with(
                user_id=self.owner.ownerid,
                event=SegmentEvent.ACCOUNT_DEACTIVATED_USER.value,
                properties={
                    "role": "admin",
                    "user": owner_to_deactivate.ownerid,
                },
                context={"groupId": org.ownerid}
            )

    @patch('analytics.track')
    def test_account_increased_users(self, track_mock):
        plan_details = {"old_quantity": 2, "new_quantity": 3, "plan": "users-inappm"}
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_increased_users(
                org_ownerid=org.ownerid,
                plan_details=plan_details,
            )
            track_mock.assert_called_once_with(
                user_id=org.ownerid,
                event=SegmentEvent.ACCOUNT_INCREASED_USERS.value,
                properties=plan_details,
                context={"groupId": org.ownerid}
            )
            
    @patch('analytics.track')
    def test_account_decreased_users(self, track_mock):
        plan_details = {"old_quantity": 3, "new_quantity": 2, "plan": "users-inappm"}
        org = OwnerFactory()
        with self.settings(SEGMENT_ENABLED=True):
            self.segment_service.account_decreased_users(
                org_ownerid=org.ownerid,
                plan_details=plan_details,
            )
            track_mock.assert_called_once_with(
                user_id=org.ownerid,
                event=SegmentEvent.ACCOUNT_DECREASED_USERS.value,
                properties=plan_details,
                context={"groupId": org.ownerid}
            )
