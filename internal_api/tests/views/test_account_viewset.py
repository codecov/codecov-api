import json
import os
from stripe.error import StripeError

from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory
from codecov_auth.models import Owner, Service
from codecov_auth.constants import USER_PLAN_REPRESENTATIONS
from internal_api.tests.test_utils import GetAdminProviderAdapter


curr_path = os.path.dirname(__file__)


class AccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "service": self.user.service,
                "owner_username": self.user.username,
            }
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(
            reverse("account_details-detail", kwargs=kwargs), data=data, format="json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "gitlab"
        self.user = OwnerFactory(stripe_customer_id=1000, service=Service.GITHUB.value)
        self.expected_invoice = {
            "number": "EF0A41E-0001",
            "status": "paid",
            "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
            "created": 1489789429,
            "period_start": 1487370220,
            "period_end": 1489789420,
            "due_date": None,
            "customer_name": "Peer Company",
            "customer_address": "6639 Boulevard Dr, Westwood FL 34202 USA",
            "currency": "usd",
            "amount_paid": 999,
            "amount_due": 999,
            "amount_remaining": 0,
            "total": 999,
            "subtotal": 999,
            "invoice_pdf": "https://pay.stripe.com/invoice/acct_1032D82eZvKYlo2C/invst_a7KV10HpLw2QxrihgVyuOkOjMZ/pdf",
            "line_items": [
                {
                    "description": "(10) users-inappm",
                    "amount": 120,
                    "currency": "usd",
                    "plan_name": "users-inappm",
                    "quantity": 1,
                    "period": {"end": 1521326190, "start": 1518906990},
                }
            ],
        }

        self.client.force_login(user=self.user)

    def test_retrieve_account_gets_account_fields(self):
        owner = OwnerFactory(admins=[self.user.ownerid])
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 0,
            "plan": {
                "marketing_name": "Basic",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 5 users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "quantity": 5,
            },
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 0,
            "student_count": 0,
        }

    def test_retrieve_account_gets_account_students(self):
        owner = OwnerFactory(
            admins=[self.user.ownerid],
            plan_activated_users=[OwnerFactory(student=True).ownerid],
        )
        student_1 = OwnerFactory(organizations=[owner.ownerid], student=True)
        student_2 = OwnerFactory(organizations=[owner.ownerid], student=True)
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 0,
            "plan": response.data["plan"],
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 1,
            "student_count": 3,
        }

    def test_account_with_free_user_plan(self):
        self.user.plan = "users-free"
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Basic",
            "value": "users-free",
            "billing_rate": None,
            "base_unit_price": 0,
            "benefits": [
                "Up to 5 users",
                "Unlimited public repositories",
                "Unlimited private repositories",
            ],
            "quantity": self.user.plan_user_count,
        }

    def test_account_with_paid_user_plan_billed_monthly(self):
        self.user.plan = "users-inappm"
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Pro Team",
            "value": "users-inappm",
            "billing_rate": "monthly",
            "base_unit_price": 12,
            "benefits": [
                "Configureable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "quantity": self.user.plan_user_count,
        }

    def test_account_with_paid_user_plan_billed_annually(self):
        self.user.plan = "users-inappy"
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Pro Team",
            "value": "users-inappy",
            "billing_rate": "annual",
            "base_unit_price": 10,
            "benefits": [
                "Configureable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "quantity": self.user.plan_user_count,
        }

    @patch("internal_api.permissions.get_provider")
    def test_retrieve_account_returns_403_if_user_not_admin(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        owner = OwnerFactory()
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_subscription_with_stripe_invoice_data(self, mock_subscription):
        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        mock_subscription.return_value = {
            "latest_invoice": json.load(f)["data"][0],
            "default_payment_method": default_payment_method,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "customer": "cus_abc",
        }

        self.user.stripe_subscription_id = "djfos"
        self.user.save()

        response = self._retrieve()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["subscription_detail"] == {
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": self.expected_invoice,
            "customer": "cus_abc",
            "default_payment_method": {
                "card": {
                    "brand": "visa",
                    "exp_month": 12,
                    "exp_year": 2024,
                    "last4": "abcd",
                }
            },
        }

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_handles_stripe_error(self, mock_get_subscription):
        code, message = 404, "Didn't find that"
        mock_get_subscription.side_effect = StripeError(
            message=message, http_status=code
        )
        self.user.stripe_subscription_id = "djfos"
        self.user.save()

        response = self._retrieve()

        assert response.status_code == code
        assert response.data["detail"] == message

    def test_update_can_set_plan_auto_activate_to_true(self):
        self.user.plan_auto_activate = False
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan_auto_activate": True},
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan_auto_activate is True
        assert response.data["plan_auto_activate"] is True

    def test_update_can_set_plan_auto_activate_to_false(self):
        self.user.plan_auto_activate = True
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan_auto_activate": False},
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan_auto_activate is False
        assert response.data["plan_auto_activate"] is False

    def test_update_can_set_plan_to_users_free(self):
        self.user.plan = "users-inappy"
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": {"value": "users-free"}},
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan == "users-free"
        assert self.user.plan_activated_users is None
        assert self.user.plan_user_count == 5
        assert response.data["plan_auto_activate"] is True

    @patch("services.billing.stripe.checkout.Session.create")
    def test_update_can_upgrade_to_paid_plan_for_new_customer_and_return_checkout_session_id(
        self,
        create_checkout_session_mock,
    ):
        expected_id = "this is the id"
        create_checkout_session_mock.return_value = {"id": expected_id}
        self.user.stripe_subscription_id = None
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": {"quantity": 25, "value": "users-pr-inappy"}},
        )

        create_checkout_session_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["checkout_session_id"] == expected_id

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    def test_update_can_upgrade_to_paid_plan_for_existing_customer_and_set_plan_info(
        self,
        modify_subscription_mock,
        retrieve_subscription_mock,
    ):
        desired_plan = {"value": "users-pr-inappm", "quantity": 12}
        self.user.stripe_customer_id = "flsoe"
        self.user.stripe_subscription_id = "djfos"
        self.user.save()

        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        retrieve_subscription_mock.return_value = {
            "items": {"data": [{"id": "abc"}]},
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "customer": self.user.stripe_customer_id,
            "latest_invoice": json.load(f)["data"][0],
            "default_payment_method": default_payment_method,
        }

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": desired_plan},
        )

        modify_subscription_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"]["value"] == desired_plan["value"]
        assert response.data["plan"]["quantity"] == desired_plan["quantity"]

        self.user.refresh_from_db()
        assert self.user.plan == desired_plan["value"]
        assert self.user.plan_user_count == desired_plan["quantity"]

    def test_update_requires_quantity_if_updating_to_paid_plan(self):
        desired_plan = {"value": "users-pr-inappy"}
        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": desired_plan},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_quantity_must_be_greater_or_equal_to_current_activated_users_if_paid_plan(
        self,
    ):
        self.user.plan_activated_users = [1] * 15
        self.user.save()
        desired_plan = {"value": "users-pr-inappy", "quantity": 14}

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_quantity_must_be_at_least_5_if_paid_plan(self):
        desired_plan = {"value": "users-pr-inappy", "quantity": 4}
        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_payment_method_without_body(self):
        kwargs = {"service": self.user.service, "owner_username": self.user.username}
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.attach")
    def test_update_payment_method(
        self, attach_payment_mock, modify_subscription_mock, retrieve_subscription_mock
    ):
        self.user.stripe_customer_id = "flsoe"
        self.user.stripe_subscription_id = "djfos"
        self.user.save()
        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        retrieve_subscription_mock.return_value = {
            "items": {"data": [{"id": "abc"}]},
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "customer": self.user.stripe_customer_id,
            "latest_invoice": json.load(f)["data"][0],
            "default_payment_method": default_payment_method,
        }
        payment_method_id = "pm_123"
        kwargs = {"service": self.user.service, "owner_username": self.user.username}
        data = {"payment_method": payment_method_id}
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK
        attach_payment_mock.assert_called_once_with(
            payment_method_id, customer=self.user.stripe_customer_id
        )
        modify_subscription_mock.assert_called_once_with(
            self.user.stripe_subscription_id, default_payment_method=payment_method_id
        )

    @patch("services.billing.StripeService.update_payment_method")
    def test_update_payment_method_handles_stripe_error(self, upm_mock):
        code, message = 402, "Oops, nope"
        self.user.stripe_customer_id = "flsoe"
        self.user.stripe_subscription_id = "djfos"
        self.user.save()

        upm_mock.side_effect = StripeError(message=message, http_status=code)

        payment_method_id = "pm_123"
        kwargs = {"service": self.user.service, "owner_username": self.user.username}
        data = {"payment_method": payment_method_id}
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("internal_api.permissions.get_provider")
    def test_update_without_admin_permissions_returns_403(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        owner = OwnerFactory()
        response = self._update(
            kwargs={"service": owner.service, "owner_username": owner.username}, data={}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_can_change_name_and_email(self):
        expected_name, expected_email = "Scooby Doo", "scoob@snack.com"
        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"name": expected_name, "email": expected_email},
        )

        assert response.data["name"] == expected_name
        assert response.data["email"] == expected_email
        self.user.refresh_from_db()
        assert self.user.name == expected_name
        assert self.user.email == expected_email

    @patch("services.billing.StripeService.modify_subscription")
    def test_update_handles_stripe_error(self, modify_sub_mock):
        code, message = 402, "Not right, wrong in fact"
        desired_plan = {"value": "users-pr-inappm", "quantity": 12}
        self.user.stripe_customer_id = "flsoe"
        self.user.stripe_subscription_id = "djfos"
        self.user.save()

        modify_sub_mock.side_effect = StripeError(message=message, http_status=code)

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": desired_plan},
        )

        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("services.task.TaskService.delete_owner")
    def test_destroy_triggers_delete_owner_task(self, delete_owner_mock):
        response = self._destroy(
            kwargs={"service": self.user.service, "owner_username": self.user.username}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_owner_mock.assert_called_once_with(self.user.ownerid)

    def test_destroy_not_own_account_returns_403(self):
        owner = OwnerFactory(admins=[self.user.ownerid])
        response = self._destroy(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("services.segment.SegmentService.account_deleted")
    @patch("services.task.TaskService.delete_owner")
    def test_destroy_triggers_segment_event(
        self, delete_owner_mock, segment_account_deleted_mock
    ):
        owner = OwnerFactory(admins=[self.user.ownerid])
        self._destroy(
            kwargs={"service": self.user.service, "owner_username": self.user.username}
        )
        segment_account_deleted_mock.assert_called_once_with(self.user)
