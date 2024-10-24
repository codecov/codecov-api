import json
from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from utils.test_utils import Client

from .helper import GraphQLTestHelper


class TestInvoiceType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.service = "gitlab"
        self.current_owner = OwnerFactory(stripe_customer_id="1000")
        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    @patch("services.billing.stripe.Invoice.list")
    def test_invoices_returns_100_recent_invoices(self, mock_list_filtered_invoices):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        # make it so there's 100 invoices, which is the max stripe returns
        stripe_invoice_response["data"] = stripe_invoice_response["data"] * 100
        mock_list_filtered_invoices.return_value = stripe_invoice_response

        query = """{
            owner(username: "%s") {
                invoices {
                    amountDue
                    amountPaid
                    created
                    currency
                    customerAddress
                    customerEmail
                    customerName
                    dueDate
                    footer
                    id
                    lineItems {
                        amount
                        currency
                        description
                    }
                    number
                    periodEnd
                    periodStart
                    status
                    subtotal
                    total
                    defaultPaymentMethod {
                        card {
                            brand
                            expMonth
                            expYear
                            last4
                        }
                        billingDetails {
                            address {
                                city
                                country
                                line1
                                line2
                                postalCode
                                state
                            }
                            email
                            name
                            phone
                        }
                    }
                    taxIds {
                        type
                        value
                    }
                }
            }
        }
        """ % (self.current_owner.username)

        data = self.gql_request(query, owner=self.current_owner)
        assert len(data["owner"]["invoices"]) == 100
        assert data["owner"]["invoices"][0] == {
            "amountDue": 999,
            "amountPaid": 999,
            "created": 1489789429,
            "currency": "usd",
            "customerAddress": "6639 Boulevard Dr, Westwood FL 34202 USA",
            "customerEmail": "olivia.williams.03@example.com",
            "customerName": "Peer Company",
            "dueDate": None,
            "footer": None,
            "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
            "lineItems": [
                {
                    "description": "(10) users-pr-inappm",
                    "amount": 120.0,
                    "currency": "usd",
                }
            ],
            "number": "EF0A41E-0001",
            "periodEnd": 1489789420,
            "periodStart": 1487370220,
            "status": "paid",
            "subtotal": 999,
            "total": 999,
            "defaultPaymentMethod": None,
            "taxIds": [],
        }

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_invoice_returns_invoice_by_id(self, mock_retrieve_invoice):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        invoice = stripe_invoice_response["data"][0]
        invoice["customer"] = self.current_owner.stripe_customer_id
        mock_retrieve_invoice.return_value = invoice

        query = """{
            owner(username: "%s") {
                invoice(invoiceId: "in_19yTU92eZvKYlo2C7uDjvu6v") {
                    amountDue
                    amountPaid
                    created
                    currency
                    customerAddress
                    customerEmail
                    customerName
                    dueDate
                    footer
                    id
                    lineItems {
                        amount
                        currency
                        description
                    }
                    number
                    periodEnd
                    periodStart
                    status
                    subtotal
                    total
                    defaultPaymentMethod {
                        card {
                            brand
                            expMonth
                            expYear
                            last4
                        }
                        billingDetails {
                            address {
                                city
                                country
                                line1
                                line2
                                postalCode
                                state
                            }
                            email
                            name
                            phone
                        }
                    }
                    taxIds {
                        type
                        value
                    }
                }
            }
        }
        """ % (self.current_owner.username)

        data = self.gql_request(query, owner=self.current_owner)
        assert data["owner"]["invoice"] is not None
        assert data["owner"]["invoice"] == {
            "amountDue": 999,
            "amountPaid": 999,
            "created": 1489789429,
            "currency": "usd",
            "customerAddress": "6639 Boulevard Dr, Westwood FL 34202 USA",
            "customerEmail": "olivia.williams.03@example.com",
            "customerName": "Peer Company",
            "dueDate": None,
            "footer": None,
            "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
            "lineItems": [
                {
                    "description": "(10) users-pr-inappm",
                    "amount": 120.0,
                    "currency": "usd",
                }
            ],
            "number": "EF0A41E-0001",
            "periodEnd": 1489789420,
            "periodStart": 1487370220,
            "status": "paid",
            "subtotal": 999,
            "total": 999,
            "defaultPaymentMethod": None,
            "taxIds": [],
        }

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_invoice_returns_none_if_no_invoices(self, mock_retrieve_invoice):
        mock_retrieve_invoice.return_value = None

        query = """{
            owner(username: "%s") {
                invoice(invoiceId: "in_19yTU92eZvKYlo2C7uDjvu6v") {
                    amountDue
                    amountPaid
                    created
                    currency
                    customerAddress
                    customerEmail
                    customerName
                    dueDate
                    footer
                    id
                    lineItems {
                        amount
                        currency
                        description
                    }
                    number
                    periodEnd
                    periodStart
                    status
                    subtotal
                    total
                    defaultPaymentMethod {
                        card {
                            brand
                            expMonth
                            expYear
                            last4
                        }
                        billingDetails {
                            address {
                                city
                                country
                                line1
                                line2
                                postalCode
                                state
                            }
                            email
                            name
                            phone
                        }
                    }
                    taxIds {
                        type
                        value
                    }
                }
            }
        }
        """ % (self.current_owner.username)

        data = self.gql_request(query, owner=self.current_owner)
        assert data["owner"]["invoice"] is None
