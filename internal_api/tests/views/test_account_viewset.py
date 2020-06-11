import json
import os
from stripe.error import StripeError

from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory
from codecov_auth.models import Owner
from codecov_auth.constants import USER_PLAN_REPRESENTATIONS


curr_path = os.path.dirname(__file__)


class AccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {"service": self.user.service, "owner_username": self.user.username}
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(reverse("account_details-detail", kwargs=kwargs), data=data, format='json')

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "gitlab"
        self.user = OwnerFactory(stripe_customer_id=1000)
        self.expected_invoice = {
            "number": "EF0A41E-0001",
            "status": "paid",
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
                "period": {
                    "end": 1521326190,
                    "start": 1518906990
                  }
              }
            ]
        }

        self.client.force_login(user=self.user)

    @patch('internal_api.owner.serializers.BillingService.list_invoices')
    def test_retrieve_account_gets_account_fields(self, _):
        owner = OwnerFactory(admins=[self.user.ownerid])
        response = self._retrieve(kwargs={"service": owner.service, "owner_username": owner.username})
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "admins": [
                {
                    "service": self.user.service,
                    "username": self.user.username,
                    "email": self.user.email,
                    "stats": self.user.cache["stats"],
                    "avatar_url": self.user.avatar_url,
                    "ownerid": self.user.ownerid,
                    "integration_id": self.user.integration_id
                }
            ],
            "activated_user_count": 0,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 0,
            "plan": None, # TODO -- legacy plan
            "recent_invoices": []
        }

    @patch('internal_api.owner.serializers.BillingService.list_invoices')
    def test_account_with_free_user_plan(self, _):
        self.user.plan = 'users-free'
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['plan'] == {
            "marketing_name": "Basic",
            "value": "users-free",
            "billing_rate": None,
            "base_unit_price": 0,
            "benefits": [
                "Up to 5 users",
                "Unlimited public repositories",
                "Unlimited private repositories"
            ]
        }

    @patch('internal_api.owner.serializers.BillingService.list_invoices')
    def test_account_with_paid_user_plan_billed_monthly(self, _):
        self.user.plan = 'users-inappm'
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['plan'] == {
            "marketing_name": "Pro Team (billed monthly)",
            "value": "users-inappm",
            "billing_rate": "monthly",
            "base_unit_price": 12,
            "benefits": [
                "Configureable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priorty Support"
            ]
        }

    @patch('internal_api.owner.serializers.BillingService.list_invoices')
    def test_account_with_paid_user_plan_billed_annually(self, _):
        self.user.plan = 'users-inappy'
        self.user.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['plan'] == {
            "marketing_name": "Pro Team (billed annually)",
            "value": "users-inappy",
            "billing_rate": "annually",
            "base_unit_price": 10,
            "benefits": [
                "Configureable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priorty Support"
            ]
        }

    def test_retrieve_account_returns_403_if_user_not_admin(self):
        owner = OwnerFactory()
        response = self._retrieve(kwargs={"service": owner.service, "owner_username": owner.username})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('services.billing.stripe.Invoice.list')
    def test_retrieve_account_with_stripe_invoice_data(self, mock_list_invoices):
        f = open("./services/tests/samples/stripe_invoice.json")
        mock_list_invoices.return_value = json.load(f)

        response = self._retrieve()
        expected_invoices = [self.expected_invoice]

        assert response.status_code == status.HTTP_200_OK
        assert response.data['recent_invoices'] == expected_invoices

    @patch('services.billing.stripe.Invoice.list')
    def test_account_raises_api_exception_if_billing_exception(self, mock_list_invoices):
        err_code, err_msg = 404, "Not Found"
        mock_list_invoices.side_effect = StripeError(message=err_msg, http_status=err_code)

        response = self._retrieve()
        assert response.status_code == err_code
        assert response.data['detail'] == err_msg

    @patch('services.billing.stripe.Invoice.list')
    def test_update_can_set_plan_auto_activate_to_true(self, _):
        self.user.plan_auto_activate = False
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan_auto_activate": True}
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan_auto_activate is True
        assert response.data['plan_auto_activate'] is True

    @patch('services.billing.stripe.Invoice.list')
    def test_update_can_set_plan_auto_activate_to_false(self, _):
        self.user.plan_auto_activate = True
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan_auto_activate": False}
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan_auto_activate is False
        assert response.data['plan_auto_activate'] is False

    @patch('services.billing.stripe.Invoice.list')
    @patch('services.billing.stripe.Subscription.delete')
    def test_update_can_set_plan_to_users_free(self, delete_sub_mock, list_inv_mock):
        self.user.plan = "users-inappy"
        self.user.save()

        response = self._update(
            kwargs={"service": self.user.service, "owner_username": self.user.username},
            data={"plan": {"value": "users-free"}}
        )

        assert response.status_code == status.HTTP_200_OK

        self.user.refresh_from_db()

        assert self.user.plan == "users-free"
        assert self.user.plan_activated_users is None
        assert self.user.plan_user_count == 5
        assert response.data["plan_auto_activate"] is True
        assert response.data["plan"] == USER_PLAN_REPRESENTATIONS["users-free"]

    def test_update_without_admin_permissions_returns_403(self):
        owner = OwnerFactory()
        response = self._update(
            kwargs={"service": owner.service, "owner_username": owner.username},
            data={}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('services.task.TaskService.delete_owner')
    def test_destroy_triggers_delete_owner_task(self, delete_owner_mock):
        owner = OwnerFactory(admins=[self.user.ownerid])
        response = self._destroy(kwargs={"service": owner.service, "owner_username": owner.username})
        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_owner_mock.assert_called_once_with(owner.ownerid)

    def test_destroy_without_admin_permissions_returns_403(self):
        owner = OwnerFactory()
        response = self._destroy(kwargs={"service": owner.service, "owner_username": owner.username})
        assert response.status_code == status.HTTP_403_FORBIDDEN
