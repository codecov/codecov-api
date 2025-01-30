from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from stripe.api_resources import PaymentIntent, SetupIntent

from .helper import GraphQLTestHelper


class BillingTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(stripe_customer_id="test-customer-id")

    def test_fetch_unverified_payment_methods(self):
        query = """
            query {
                owner(username: "%s") {
                    billing {
                        unverifiedPaymentMethods {
                            paymentMethodId
                            hostedVerificationUrl
                        }
                    }
                }
            }
        """ % (self.owner.username)

        payment_intent = PaymentIntent.construct_from(
            {
                "payment_method": "pm_123",
                "next_action": {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": "https://verify.stripe.com/1"
                    },
                },
            },
            "fake_api_key",
        )

        setup_intent = SetupIntent.construct_from(
            {
                "payment_method": "pm_456",
                "next_action": {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": "https://verify.stripe.com/2"
                    },
                },
            },
            "fake_api_key",
        )

        with (
            patch(
                "services.billing.stripe.PaymentIntent.list"
            ) as payment_intent_list_mock,
            patch("services.billing.stripe.SetupIntent.list") as setup_intent_list_mock,
        ):
            payment_intent_list_mock.return_value.data = [payment_intent]
            payment_intent_list_mock.return_value.has_more = False
            setup_intent_list_mock.return_value.data = [setup_intent]
            setup_intent_list_mock.return_value.has_more = False

            result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        data = result["owner"]["billing"]["unverifiedPaymentMethods"]
        assert len(data) == 2
        assert data[0]["paymentMethodId"] == "pm_123"
        assert data[0]["hostedVerificationUrl"] == "https://verify.stripe.com/1"
        assert data[1]["paymentMethodId"] == "pm_456"
        assert data[1]["hostedVerificationUrl"] == "https://verify.stripe.com/2"
