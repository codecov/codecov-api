import logging

import stripe

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner
from services.billing import BillingService

log = logging.getLogger(__name__)


class CreateStripeSetupIntentInteractor(BaseInteractor):
    def validate(self, owner_obj: Owner) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner_obj:
            raise ValidationError("Owner not found")
        if not current_user_part_of_org(self.current_owner, owner_obj):
            raise Unauthorized()

    def create_setup_intent(self, owner_obj: Owner) -> stripe.SetupIntent:
        try:
            billing = BillingService(requesting_user=self.current_owner)
            return billing.create_setup_intent(owner_obj)
        except Exception as e:
            log.error(
                "Error getting setup intent",
                extra={
                    "ownerid": owner_obj.ownerid,
                    "error": str(e),
                },
            )
            raise ValidationError("Unable to create setup intent")

    @sync_to_async
    def execute(self, owner: str) -> stripe.SetupIntent:
        owner_obj = Owner.objects.filter(username=owner, service=self.service).first()
        self.validate(owner_obj)
        return self.create_setup_intent(owner_obj)
