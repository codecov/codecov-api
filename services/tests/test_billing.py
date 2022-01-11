from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from stripe.error import InvalidRequestError, StripeError

from codecov_auth.models import Service
from codecov_auth.tests.factories import OwnerFactory
from services.billing import AbstractPaymentService, BillingService, StripeService

SCHEDULE_RELEASE_OFFSET = 10


class MockSubscription(object):
    def __init__(self, subscription_params):
        self.schedule = subscription_params["schedule_id"]
        self.current_period_start = subscription_params["start_date"]
        self.current_period_end = subscription_params["end_date"]
        self.items = {
            "data": [
                {
                    "quantity": subscription_params["quantity"],
                    "id": subscription_params["id"],
                    "plan": {"name": subscription_params["name"]},
                }
            ]
        }

    def __getitem__(self, key):
        return getattr(self, key)


class StripeServiceTests(TestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.stripe = StripeService(requesting_user=self.user)

    def test_stripe_service_requires_requesting_user_to_be_owner_instance(self):
        with self.assertRaises(Exception):
            StripeService(None)

    @patch("services.billing.stripe.Invoice.list")
    def test_list_invoices_calls_stripe_invoice_list_with_customer_stripe_id(
        self, invoice_list_mock
    ):
        owner = OwnerFactory(stripe_customer_id=-1)
        self.stripe.list_invoices(owner)
        invoice_list_mock.assert_called_once_with(
            customer=owner.stripe_customer_id, limit=10
        )

    @patch("stripe.Invoice.list")
    def test_list_invoices_returns_emptylist_if_stripe_customer_id_is_None(
        self, invoice_list_mock
    ):
        owner = OwnerFactory()
        invoices = self.stripe.list_invoices(owner)

        invoice_list_mock.assert_not_called()
        assert invoices == []

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.billing.stripe.Subscription.delete")
    @patch("services.billing.stripe.Subscription.modify")
    def test_delete_subscription_deletes_and_prorates_if_owner_not_on_user_plan(
        self, modify_mock, delete_mock, set_basic_plan_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="fowdldjfjwe", plan="v4-50m")
        self.stripe.delete_subscription(owner)
        delete_mock.assert_called_once_with(owner.stripe_subscription_id, prorate=False)
        set_basic_plan_mock.assert_called_once()

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.billing.stripe.Subscription.delete")
    @patch("services.billing.stripe.Subscription.modify")
    def test_delete_subscription_modifies_subscription_to_delete_at_end_of_billing_cycle_if_user_plan(
        self, modify_mock, delete_mock, set_basic_plan_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="fowdldjfjwe", plan="users-inappy")
        self.stripe.delete_subscription(owner)
        delete_mock.assert_not_called()
        set_basic_plan_mock.assert_not_called()
        modify_mock.assert_called_once_with(
            owner.stripe_subscription_id, cancel_at_period_end=True, prorate=False
        )

    @patch("services.segment.SegmentService.account_increased_users")
    @patch("services.segment.SegmentService.account_changed_plan")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_increases_user_count_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
        segment_changed_plan_mock,
        segment_increase_users_mock,
    ):
        original_user_count = 10
        original_plan = "users-pr-inappy"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 105,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappy"
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        subscription_modify_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription_params["id"],
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"],
                }
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="always_invoice",
        )

        segment_changed_plan_mock.assert_not_called()
        segment_increase_users_mock.assert_called_with(
            current_user_ownerid=self.user.ownerid,
            org_ownerid=owner.ownerid,
            plan_details={
                "new_quantity": desired_user_count,
                "old_quantity": original_user_count,
                "plan": desired_plan_name,
            },
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.segment.SegmentService.account_increased_users")
    @patch("services.segment.SegmentService.account_changed_plan")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_upgrades_plan_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
        segment_changed_plan_mock,
        segment_increase_users_mock,
    ):
        original_plan = "users-pr-inappm"
        original_user_count = 10
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 101,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappy"
        desired_user_count = 10
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        subscription_modify_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription_params["id"],
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"],
                }
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="always_invoice",
        )

        segment_increase_users_mock.assert_not_called()
        segment_changed_plan_mock.assert_called_with(
            current_user_ownerid=self.user.ownerid,
            org_ownerid=owner.ownerid,
            plan_details={
                "new_plan": desired_plan_name,
                "previous_plan": original_plan,
            },
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.segment.SegmentService.account_increased_users")
    @patch("services.segment.SegmentService.account_changed_plan")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_upgrades_plan_and_users_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
        segment_changed_plan_mock,
        segment_increase_users_mock,
    ):
        original_user_count = 10
        original_plan = "users-pr-inappm"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 102,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappy"
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        subscription_modify_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription_params["id"],
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"],
                }
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="always_invoice",
        )

        segment_increase_users_mock.assert_called_with(
            current_user_ownerid=self.user.ownerid,
            org_ownerid=owner.ownerid,
            plan_details={
                "new_quantity": desired_user_count,
                "old_quantity": original_user_count,
                "plan": desired_plan_name,
            },
        )
        segment_changed_plan_mock.assert_called_with(
            current_user_ownerid=self.user.ownerid,
            org_ownerid=owner.ownerid,
            plan_details={
                "new_plan": desired_plan_name,
                "previous_plan": original_plan,
            },
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_user_count_decreases(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 14
        original_plan = "users-pr-inappm"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 104,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 8
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_plan_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 20
        original_plan = "users-pr-inappy"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 106,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_plan_and_count_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 16
        original_plan = "users-pr-inappy"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 107,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 7
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_user_count_decreases(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 13
        original_plan = "users-pr-inappm"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRnne"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 108,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 9
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_user_count_increases(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 17
        original_plan = "users-pr-inappm"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 26

        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRnne"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 109,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 26
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_plan_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 15
        original_plan = "users-pr-inappy"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 110,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_plan_upgrades(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 15
        original_plan = "users-pr-inappm"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 111,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappy"
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_plan_upgrades_and_count_decreases(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 15
        original_plan = "users-pr-inappm"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 112,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappy"
        desired_user_count = 10
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_plan_downgrades_and_count_increases(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 15
        original_plan = "users-pr-inappy"
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 113,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = "users-pr-inappm"
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[original_plan],
                            "price": settings.STRIPE_PLAN_IDS[original_plan],
                            "quantity": original_user_count,
                        }
                    ],
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_user_count,
                        }
                    ],
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    def test_get_proration_params(self):
        # Test same plan, increased users
        owner = OwnerFactory(plan="users-pr-inappy", plan_user_count=10)
        desired_plan = {"value": "users-pr-inappy", "quantity": 14}
        self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"

        # Test same plan, drecrease users
        owner = OwnerFactory(plan="users-pr-inappy", plan_user_count=20)
        desired_plan = {"value": "users-pr-inappy", "quantity": 14}
        self.stripe._get_proration_params(owner, desired_plan) == "none"

        # Test going from monthly to yearly
        owner = OwnerFactory(plan="users-pr-inappm", plan_user_count=20)
        desired_plan = {"value": "users-pr-inappy", "quantity": 14}
        self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_creates_with_correct_args_and_returns_id(
        self, create_checkout_session_mock
    ):
        owner = OwnerFactory(service=Service.GITHUB.value)
        expected_id = "fkkgosd"
        create_checkout_session_mock.return_value = {
            "id": expected_id
        }  # only field relevant to implementation
        desired_quantity = 25
        desired_plan = {"value": "users-pr-inappm", "quantity": desired_quantity}

        assert self.stripe.create_checkout_session(owner, desired_plan) == expected_id

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_types=["card"],
            client_reference_id=owner.ownerid,
            customer=owner.stripe_customer_id,
            customer_email=owner.email,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/account/gh/{owner.username}/billing?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/account/gh/{owner.username}/billing?cancel",
            subscription_data={
                "items": [
                    {
                        "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                        "quantity": desired_quantity,
                    }
                ],
                "payment_behavior": "allow_incomplete",
                "metadata": {
                    "service": owner.service,
                    "obo_organization": owner.ownerid,
                    "username": owner.username,
                    "obo_name": self.user.name,
                    "obo_email": self.user.email,
                    "obo": self.user.ownerid,
                },
            },
        )

    def test_get_subscription_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.get_subscription(owner) == None

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_get_subscription_returns_stripe_data(self, subscription_retrieve_mock):
        owner = OwnerFactory(stripe_subscription_id="abc")
        # only including fields relevant to implementation
        stripe_data_subscription = {"doesnt": "matter"}
        payment_method_id = "pm_something_something"
        subscription_retrieve_mock.return_value = stripe_data_subscription
        assert self.stripe.get_subscription(owner) == stripe_data_subscription
        subscription_retrieve_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            expand=[
                "latest_invoice",
                "customer",
                "customer.invoice_settings.default_payment_method",
            ],
        )

    def test_update_payment_method_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_payment_method(owner, "abc") == None

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_payment_method(self, modify_customer_mock, attach_payment_mock):
        payment_method_id = "pm_1234567"
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )
        self.stripe.update_payment_method(owner, payment_method_id)
        attach_payment_mock.assert_called_once_with(
            payment_method_id, customer=customer_id
        )
        modify_customer_mock.assert_called_once_with(
            customer_id, invoice_settings={"default_payment_method": payment_method_id}
        )

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_not_found(self, retrieve_invoice_mock):
        invoice_id = "abc"
        retrieve_invoice_mock.side_effect = InvalidRequestError(
            message="not found", param=invoice_id
        )
        assert self.stripe.get_invoice(OwnerFactory(), invoice_id) == None
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_customer_dont_match(self, retrieve_invoice_mock):
        owner = OwnerFactory(stripe_customer_id="something_very_very_random_cus_abc")
        invoice_id = "abc"
        invoice = {"invoice_id": "abc", "customer": "cus_abc"}
        retrieve_invoice_mock.return_value = invoice
        assert self.stripe.get_invoice(owner, invoice_id) == None
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice(self, retrieve_invoice_mock):
        customer_id = "cus_abc"
        owner = OwnerFactory(stripe_customer_id=customer_id)
        invoice_id = "abc"
        invoice = {"invoice_id": "abc", "customer": customer_id}
        retrieve_invoice_mock.return_value = invoice
        assert self.stripe.get_invoice(owner, invoice_id) == invoice
        retrieve_invoice_mock.assert_called_once_with(invoice_id)


class MockPaymentService(AbstractPaymentService):
    def list_invoices(self, owner, limit=10):
        return f"{owner.ownerid} {limit}"

    def get_invoice(self, owner, id):
        pass

    def delete_subscription(self, owner):
        pass

    def modify_subscription(self, owner, plan):
        pass

    def create_checkout_session(self, owner, plan):
        pass

    def get_subscription(self, owner, plan):
        pass

    def update_payment_method(self, owner, plan):
        pass


class BillingServiceTests(TestCase):
    def setUp(self):
        self.mock_payment_service = MockPaymentService()
        self.billing_service = BillingService(payment_service=self.mock_payment_service)

    def test_default_payment_service_is_stripe(self):
        requesting_user = OwnerFactory()
        assert isinstance(
            BillingService(requesting_user=requesting_user).payment_service,
            StripeService,
        )

    def test_list_invoices_calls_payment_service_list_invoices_with_limit(self):
        owner = OwnerFactory()
        assert self.billing_service.list_invoices(
            owner
        ) == self.mock_payment_service.list_invoices(owner)

    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_to_users_basic_deletes_subscription_if_user_has_stripe_subscription(
        self, delete_subscription_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="tor_dsoe")
        self.billing_service.update_plan(owner, {"value": "users-basic"})
        delete_subscription_mock.assert_called_once_with(owner)

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_to_users_basic_sets_plan_if_no_subscription_id(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_basic_plan_mock,
    ):
        owner = OwnerFactory()
        self.billing_service.update_plan(owner, {"value": "users-basic"})

        set_basic_plan_mock.assert_called_once()

        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_modifies_subscription_if_user_plan_and_subscription_exists(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_basic_plan_mock,
    ):
        owner = OwnerFactory(stripe_subscription_id=10)
        desired_plan = {"value": "users-pr-inappy", "quantity": 10}
        self.billing_service.update_plan(owner, desired_plan)

        modify_subscription_mock.assert_called_once_with(owner, desired_plan)

        set_basic_plan_mock.assert_not_called()
        delete_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_creates_checkout_session_if_user_plan_and_no_subscription(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_basic_plan_mock,
    ):
        owner = OwnerFactory(stripe_subscription_id=None)
        desired_plan = {"value": "users-pr-inappy", "quantity": 10}
        self.billing_service.update_plan(owner, desired_plan)

        create_checkout_session_mock.assert_called_once_with(owner, desired_plan)

        set_basic_plan_mock.assert_not_called()
        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()

    @patch("codecov_auth.models.Owner.set_basic_plan")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_does_nothing_if_not_switching_to_user_plan(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_basic_plan_mock,
    ):
        owner = OwnerFactory()
        desired_plan = {"value": "v4-50m"}
        self.billing_service.update_plan(owner, desired_plan)

        set_basic_plan_mock.assert_not_called()
        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("services.tests.test_billing.MockPaymentService.get_subscription")
    def test_get_subscription(self, get_subscription_mock):
        owner = OwnerFactory()
        self.billing_service.get_subscription(owner)
        get_subscription_mock.assert_called_once_with(owner)

    @patch("services.tests.test_billing.MockPaymentService.update_payment_method")
    def test_update_payment_method(self, get_subscription_mock):
        owner = OwnerFactory()
        self.billing_service.update_payment_method(owner, "abc")
        get_subscription_mock.assert_called_once_with(owner, "abc")

    @patch("services.tests.test_billing.MockPaymentService.get_invoice")
    def test_get_invoice(self, get_invoice_mock):
        owner = OwnerFactory()
        self.billing_service.get_invoice(owner, "abc")
        get_invoice_mock.assert_called_once_with(owner, "abc")
