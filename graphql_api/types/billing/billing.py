from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from codecov_auth.models import Owner
from services.billing import BillingService

billing_bindable = ObjectType("Billing")


@billing_bindable.field("unverifiedPaymentMethods")
def resolve_unverified_payment_methods(
    owner: Owner, info: GraphQLResolveInfo
) -> list[dict]:
    return BillingService(requesting_user=owner).get_unverified_payment_methods(owner)
