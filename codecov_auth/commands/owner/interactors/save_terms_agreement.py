from dataclasses import dataclass
from typing import Any, Optional

from django.utils import timezone

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from services.analytics import AnalyticsService


@dataclass
class TermsAgreementInput:
    business_email: Optional[str] = None
    name: Optional[str] = None
    terms_agreement: bool = False
    marketing_consent: bool = False
    customer_intent: Optional[str] = None


class SaveTermsAgreementInteractor(BaseInteractor):
    requires_service = False

    def validate_deprecated(self, input: TermsAgreementInput) -> None:
        valid_customer_intents = ["Business", "BUSINESS", "Personal", "PERSONAL"]
        if (
            input.customer_intent
            and input.customer_intent not in valid_customer_intents
        ):
            raise ValidationError("Invalid customer intent provided")
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def validate(self, input: TermsAgreementInput) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def update_terms_agreement_deprecated(self, input: TermsAgreementInput) -> None:
        self.current_user.terms_agreement = input.terms_agreement
        self.current_user.terms_agreement_at = timezone.now()
        self.current_user.customer_intent = input.customer_intent
        self.current_user.email_opt_in = input.marketing_consent
        self.current_user.save()

        if input.business_email and input.business_email != "":
            self.current_user.email = input.business_email
            self.current_user.save()

        if input.marketing_consent:
            self.send_data_to_marketo()

    def update_terms_agreement(self, input: TermsAgreementInput) -> None:
        self.current_user.terms_agreement = input.terms_agreement
        self.current_user.terms_agreement_at = timezone.now()
        self.current_user.name = input.name
        self.current_user.email_opt_in = input.marketing_consent
        self.current_user.save()

        if input.business_email and input.business_email != "":
            self.current_user.email = input.business_email
            self.current_user.save()

        if input.marketing_consent:
            self.send_data_to_marketo()

    def send_data_to_marketo(self) -> None:
        event_data = {
            "email": self.current_user.email,
        }
        AnalyticsService().opt_in_email(self.current_user.id, event_data)

    @sync_to_async
    def execute(self, input: Any) -> None:
        if input.get("name"):
            typed_input = TermsAgreementInput(
                business_email=input.get("business_email"),
                terms_agreement=input.get("terms_agreement"),
                marketing_consent=input.get("marketing_consent"),
                name=input.get("name"),
            )
            self.validate(typed_input)
            self.update_terms_agreement(typed_input)
        # this handles the deprecated inputs
        else:
            typed_input = TermsAgreementInput(
                business_email=input.get("business_email"),
                terms_agreement=input.get("terms_agreement"),
                marketing_consent=input.get("marketing_consent"),
                customer_intent=input.get("customer_intent"),
            )
            self.validate_deprecated(typed_input)
            self.update_terms_agreement_deprecated(typed_input)
