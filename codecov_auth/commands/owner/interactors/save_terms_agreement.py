from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from services.analytics import AnalyticsService


@dataclass
class TermsAgreementInput:
    business_email: Optional[str] = None
    terms_agreement: bool = False
    marketing_consent: bool = False
    customer_intent: str = None


class SaveTermsAgreementInteractor(BaseInteractor):
    requires_service = False

    def validate(self, input: TermsAgreementInput):
        if input.terms_agreement is None:
            raise ValidationError("Terms of agreement cannot be null")
        if input.customer_intent not in [
            "Business",
            "Business",
            "Personal",
            "PERSONAL",
        ]:
            raise ValidationError("Invalid customer intent provided")
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def update_terms_agreement(self, input: TermsAgreementInput):
        self.current_user.terms_agreement = input.terms_agreement
        self.current_user.terms_agreement_at = timezone.now()
        self.current_user.save()
        self.current_user.customer_intent = input.customer_intent

        if input.business_email is not None and input.business_email != "":
            self.current_user.email = input.business_email
            self.current_user.save()

        self.send_data_to_marketo()

    def send_data_to_marketo(self):
        event_data = {
            "email": self.current_user.email,
        }
        AnalyticsService().opt_in_email(self.current_user.id, event_data)

    @sync_to_async
    def execute(self, input):
        typed_input = TermsAgreementInput(
            business_email=input.get("businessEmail"),
            terms_agreement=input.get("termsAgreement"),
            marketing_consent=input.get("marketingConsent"),
            customer_intent=input.get("customerIntent"),
        )
        self.validate(typed_input)
        return self.update_terms_agreement(typed_input)
