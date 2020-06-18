import json
import os
from stripe.error import StripeError

from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory


curr_path = os.path.dirname(__file__)


class InvoiceViewSetTests(APITestCase):
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

    def _list(self, kwargs):
        return self.client.get(reverse("invoices-list", kwargs=kwargs))

    @patch('services.billing.stripe.Invoice.list')
    def test_invoices_returns_100_recent_invoices(self, mock_list_invoices):
        f = open("./services/tests/samples/stripe_invoice.json")
        stripe_invoice_response = json.load(f)
        # make it so there's 100 invoices, which is the max stripe returns
        stripe_invoice_response["data"] = stripe_invoice_response["data"] * 100
        mock_list_invoices.return_value = stripe_invoice_response
        expected_invoices = [self.expected_invoice] * 100

        response = self._list(kwargs={"service": self.user.service, "owner_username": self.user.username})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 100
        assert response.data == expected_invoices

    def test_invoices_returns_403_if_user_not_admin(self):
        owner = OwnerFactory()
        response = self._list(kwargs={"service": owner.service, "owner_username": owner.username})
        assert response.status_code == status.HTTP_403_FORBIDDEN
